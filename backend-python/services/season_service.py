from datetime import datetime, timezone, timedelta
from database.db import SessionLocal
from models.race import Race
from models.analytics import DataSyncRun

def utcnow(): return datetime.now(timezone.utc)
def iso(value): return value.astimezone(timezone.utc).isoformat()
def parse_time(value):
    if not value: return None
    dt = datetime.fromisoformat(value.replace('Z','+00:00'))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
def race_start(race):
    return parse_time(race.start_at) or datetime.combine(race.date, datetime.min.time(), tzinfo=timezone.utc)

class SeasonContext:
    def get(self, now=None):
        now = now or utcnow()
        with SessionLocal() as s:
            races = s.query(Race).order_by(Race.date, Race.round).all()
            seasons = sorted({r.season_year for r in races})
            relevant = [y for y in seasons if y <= now.year]
            active = max(relevant) if relevant else now.year
            completed = [r for r in races if r.results_verified and r.is_completed and r.race_status == 'COMPLETED' and r.date and race_start(r)<=now]
            latest = completed[-1] if completed else None
            upcoming = [r for r in races if r.season_year==active and not r.is_completed and r.race_status=='SCHEDULED' and r.date and race_start(r)>now]
            pending = [r for r in races if r.season_year==active and not r.is_completed and r.race_status=='SCHEDULED' and r.date and race_start(r)<=now]
            sync = s.query(DataSyncRun).filter_by(season=active, status='SUCCESS').order_by(DataSyncRun.id.desc()).first()
            return {'active_season':active,'seasons':seasons,'latest_completed_race':latest.to_dict() if latest else None,'next_race':upcoming[0].to_dict() if upcoming else None,'last_sync_at':sync.completed_at if sync else None,'awaiting_results':[r.to_dict() for r in pending], 'as_of':iso(now), 'stale':not sync or (now-parse_time(sync.completed_at)).total_seconds()>86400}
