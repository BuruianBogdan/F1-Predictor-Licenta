"""Manual weekend refresh using the original Race Control and prediction services."""
import copy
import json
import logging
import threading
import time
from datetime import timedelta
from services.job_service import JobService
from services.season_service import SeasonContext, parse_time, utcnow, iso
from services.race_control_service import RaceControlService, CODES
from services.weekend_service import WeekendService

LOG = logging.getLogger(__name__)


class SessionRefreshService:
    def __init__(self, service=None, weekend=None):
        self.service = service or RaceControlService()
        self.weekend = weekend or WeekendService()
        self.lock = threading.RLock()
        self.work_lock = threading.Lock()
        self.shutdown_event = threading.Event()
        self.job_id = None
        self.progress = {}

    def refresh(self, race_id=None):
        with self.lock:
            current = JobService.jobs.get(self.job_id, {})
            if current.get('status') in ('QUEUED', 'RUNNING'):
                return self.status()
            self.progress = {'phase': 'QUEUED', 'message': 'Checking all weekend sessions'}
            job = JobService.submit('Refresh all weekend sessions', lambda: self.tick(force=True, race_id=race_id, progress=self.update_progress))
            self.job_id = job['id']
            return self.status()

    def status(self):
        with self.lock:
            job = JobService.jobs.get(self.job_id, {})
            return {**copy.deepcopy(job), 'status': job.get('status', 'IDLE'), 'progress': copy.deepcopy(self.progress)}

    def update_progress(self, value):
        with self.lock:
            self.progress = copy.deepcopy(value)

    def catalog(self, race_id, force=False):
        path = self.service.cache_dir / f'session-catalog-{race_id}.json' if hasattr(self.service, 'cache_dir') else None
        if path and not self.service.catalogs.get(race_id, {}).get('rows') and path.exists():
            try:
                saved = json.loads(path.read_text())
                race, _ = self.service.race_info(race_id)
                rows = saved['rows']
                gps = [m for m in rows if m.get('session_name') == 'Race' and parse_time(m['date_start']).date().isoformat() == race['date']]
                if (saved['race_id'] == race_id and saved['date'] == race['date'] and saved['season_year'] == race['season_year']
                        and len(gps) == 1 and all(m['meeting_key'] == gps[0]['meeting_key'] and m['session_name'] in CODES for m in rows)):
                    self.service.catalogs[race_id] = {'rows': rows, 'checked': -1e10, 'error': None}
            except (OSError, ValueError, KeyError, TypeError):
                pass
        catalog = self.service.catalog(race_id, refresh=True) if force else self.service.catalog(race_id)
        if path and catalog['sessions']:
            data = {'race_id': race_id, 'date': catalog['race']['date'], 'season_year': catalog['race']['season_year'],
                    'checked_at': catalog['as_of'], 'rows': catalog['sessions']}
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(data))
            temp.replace(path)
        return catalog

    def tick(self, force=False, race_id=None, progress=None):
        if not self.work_lock.acquire(blocking=force):
            return {'status': 'BUSY'}
        try:
            return self._tick(force, race_id, progress or (lambda _: None))
        finally:
            self.work_lock.release()

    def _tick(self, force, race_id, progress):
        now = utcnow()
        context = SeasonContext().get()
        pending = [r for r in context.get('awaiting_results', []) if parse_time(r['start_at']) >= now - timedelta(days=3)]
        race = max(pending, key=lambda r: r['start_at']) if pending else context.get('next_race')
        if race_id is not None:
            race, _ = self.service.race_info(int(race_id))
        elif not race:
            race = context.get('latest_completed_race')
        if not race:
            return {'status': 'NO_WEEKEND', 'message': 'No weekend is available in the synchronized calendar', 'sessions': []}
        rid = race['race_id']
        warnings = []
        progress({'phase': 'CATALOG', 'message': 'Checking the published session schedule', 'race_name': race.get('race_name'), 'sessions': []})
        catalog = self.catalog(rid, force)
        sessions = catalog['sessions']
        if catalog.get('error'):
            warnings.append(catalog['error'])
        if not sessions and not warnings:
            warnings.append('No sessions are published for this weekend yet')
        ready = [s for s in sessions if s['state'] == 'REPLAY']
        if ready:
            progress({'phase': 'RESULTS', 'message': 'Checking published classifications and recalculating predictions', 'race_name': race.get('race_name'), 'sessions': self.rows(rid, sessions)})
            try:
                if parse_time(race['start_at']) > now:
                    result = self.weekend.refresh(rid, force=True)
                    if isinstance(result, dict) and result.get('status') in ('FAILED', 'PARTIAL'):
                        warnings.append('Some classifications are not published yet; earlier results have been preserved')
                elif any(s['session_name'] == 'Race' for s in ready) and not race.get('results_verified'):
                    from services.data_sync_service import F1DataSyncService
                    F1DataSyncService().sync_season(race['season_year'])
            except Exception as exc:
                warnings.append(str(exc))
                LOG.warning('Published weekend update deferred: %s', exc)
        for item in sorted(ready, key=lambda s: s['date_start'], reverse=True):
            key = item['session_key']
            if self.service.covered(self.service.load(key)):
                continue
            try:
                job = self.service.prepare(rid, key, 'REPLAY')
                deadline = time.monotonic() + 900
                while job.get('status') in ('QUEUED', 'RUNNING'):
                    progress({'phase': 'ARCHIVE', 'message': item['session_name'] + ': ' + job.get('progress', 'Downloading'), 'race_name': race.get('race_name'), 'sessions': self.rows(rid, sessions)})
                    if self.shutdown_event.wait(1):
                        raise ValueError('Application stopped before the download finished')
                    if time.monotonic() > deadline:
                        raise ValueError('Archive is still downloading; its progress remains available in Race Control')
                    job = self.service.status(rid, key, 'REPLAY')
                if job.get('status') != 'SUCCESS':
                    warnings.append(item['session_name'] + ': ' + job.get('error', 'Archive is not published yet'))
            except Exception as exc:
                warnings.append(item['session_name'] + ': ' + str(exc))
        result = {'status': 'PARTIAL' if warnings else 'SUCCESS', 'race_id': rid, 'race_name': race.get('race_name'),
                  'checked_at': iso(utcnow()), 'sessions': self.rows(rid, sessions), 'warnings': list(dict.fromkeys(warnings)),
                  'message': 'All weekend sessions checked; only publicly available archives can be downloaded'}
        progress({'phase': 'COMPLETE', **result})
        return result

    def rows(self, race_id, sessions):
        rows = []
        for item in sessions:
            key = item['session_key']
            downloaded = self.service.covered(self.service.load(key))
            job = self.service.jobs.get(f'{key}-REPLAY', {})
            viewer = f"/race-control/{race_id}?session={item['code']}&autostart=true"
            rows.append({'session_key': key, 'race_id': race_id, 'name': item['session_name'],
                         'starts_at': item['date_start'], 'archive_at': item['archive_at'], 'downloaded': bool(downloaded),
                         'status': 'DOWNLOADED' if downloaded else 'DOWNLOADING' if job.get('status') in ('RUNNING', 'QUEUED') else item['state'],
                         'viewer_url': viewer, 'replay_url': viewer if downloaded else None})
        return rows
