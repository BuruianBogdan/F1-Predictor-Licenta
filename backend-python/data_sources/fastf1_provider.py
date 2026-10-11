"""Explicit, cached session enrichment. No telemetry unless requested."""
import json
from config import FASTF1_CACHE_DIR
from data_sources.base_provider import ProviderError

class FastF1Provider:
    name='fastf1'
    def _api(self):
        try: import fastf1
        except ImportError as exc: raise ProviderError('Install requirements-dev.txt for FastF1 enrichment') from exc
        FASTF1_CACHE_DIR.mkdir(parents=True,exist_ok=True)
        fastf1.Cache.enable_cache(str(FASTF1_CACHE_DIR))
        return fastf1
    def fetch_schedule(self, year):
        schedule=self._api().get_event_schedule(year, include_testing=False)
        return json.loads(schedule.to_json(orient='records',date_format='iso'))
    def fetch_session(self, year, round_number, session='Q', telemetry=False, laps=False):
        if session not in ('FP1','FP2','FP3','Q','R','S','SQ'): raise ValueError('Unknown session')
        api=self._api();data=api.get_session(year,round_number,session)
        data.load(laps=laps or telemetry,telemetry=telemetry,weather=True,messages=False)
        payload={'results':json.loads(data.results.to_json(orient='records',date_format='iso')),'weather':json.loads(data.weather_data.to_json(orient='records',date_format='iso')),'telemetry_loaded':telemetry}
        if laps or telemetry:
            selected=[c for c in ('Driver','LapNumber','LapTime','Compound','TyreLife','IsAccurate') if c in data.laps]
            payload['laps']=json.loads(data.laps[selected].to_json(orient='records',date_format='iso'))
        return payload
