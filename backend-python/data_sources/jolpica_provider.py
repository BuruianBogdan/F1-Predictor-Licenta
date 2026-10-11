"""Jolpica's limit applies to nested result rows, not the number of races."""
import hashlib
import json
import threading
import time
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import JOLPICA_BASE_URL, HTTP_TIMEOUT, DATA_DIR
from data_sources.base_provider import F1Provider, ProviderError

class JolpicaProvider(F1Provider):
    name = 'jolpica'
    _lock = threading.Lock()
    _last_request = 0.0

    def __init__(self, session=None, cache=True):
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent':'F1Predictor/2.0'})
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504], allowed_methods=['GET'], respect_retry_after_header=True)
        self.session.mount('https://', HTTPAdapter(max_retries=retry))
        self.cache = cache

    def _get(self, path, offset):
        url = f'{JOLPICA_BASE_URL}/{path.strip("/")}/'
        key = hashlib.sha256(f'{url}|{offset}'.encode()).hexdigest()
        file = DATA_DIR / 'cache/jolpica' / f'{key}.json'
        if self.cache and file.exists() and time.time()-file.stat().st_mtime < 300:
            return json.loads(file.read_text())
        with self._lock:
            pause = 0.3 - (time.monotonic()-self.__class__._last_request)
            if pause > 0: time.sleep(pause)
            self.__class__._last_request = time.monotonic()
        try:
            response = self.session.get(url, params={'limit':100,'offset':offset}, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            data = response.json()['MRData']
            if not isinstance(data, dict): raise ValueError('Invalid MRData')
        except (requests.RequestException, ValueError, KeyError) as exc:
            raise ProviderError(f'Jolpica request failed for {path} (offset {offset}): {type(exc).__name__}') from exc
        if self.cache:
            file.parent.mkdir(parents=True, exist_ok=True)
            temp = file.with_suffix('.tmp')
            temp.write_text(json.dumps(data)); temp.replace(file)
        return data

    def _pages(self, path, table, collection, nested=None):
        offset, rows = 0, []
        for _ in range(200):
            data = self._get(path, offset)
            try:
                page = data[table][collection]
                total, limit = int(data['total']), int(data['limit'])
                actual_offset = int(data.get('offset', offset))
            except (KeyError, ValueError, TypeError) as exc:
                raise ProviderError(f'Malformed pagination at {path}') from exc
            if actual_offset != offset or limit <= 0 or (not page and offset < total):
                raise ProviderError(f'Incomplete pagination at {path}')
            rows.extend(page)
            offset += limit
            if offset >= total: break
        else:
            raise ProviderError('Pagination limit exceeded')
        if not nested: return rows
        merged = {}
        for row in rows:
            key = (row.get('season'), row.get('round'))
            if key not in merged: merged[key] = {**row,nested:[]}
            merged[key][nested].extend(row.get(nested, []))
        return list(merged.values())

    def fetch_races(self, season): return self._pages(f'{season}/races','RaceTable','Races')
    def fetch_results(self, season): return self._pages(f'{season}/results','RaceTable','Races','Results')
    def fetch_drivers(self, season): return self._pages(f'{season}/drivers','DriverTable','Drivers')
    def fetch_constructors(self, season): return self._pages(f'{season}/constructors','ConstructorTable','Constructors')
    def fetch_circuits(self, season): return self._pages(f'{season}/circuits','CircuitTable','Circuits')
    def fetch_qualifying(self, season): return self._pages(f'{season}/qualifying','RaceTable','Races','QualifyingResults')
    def fetch_sprints(self, season): return self._pages(f'{season}/sprint','RaceTable','Races','SprintResults')
    def fetch_standings(self, season, kind):
        key = 'DriverStandings' if kind == 'drivers' else 'ConstructorStandings'
        endpoint = 'driverstandings' if kind == 'drivers' else 'constructorstandings'
        return self._pages(f'{season}/{endpoint}','StandingsTable','StandingsLists',key)
