from sqlalchemy import text
from database.db import engine
from services.season_service import iso, utcnow

class DataQualityService:
    def report(self):
        queries={
            'missing_grids':'SELECT count(*) FROM race_results WHERE grid IS NULL',
            'missing_positions':'SELECT count(*) FROM race_results WHERE position IS NULL',
            'missing_driver_refs':"SELECT count(*) FROM drivers WHERE driver_ref IS NULL OR trim(driver_ref)=''",
            'missing_constructors':'SELECT count(*) FROM race_results x LEFT JOIN constructors c USING(constructor_id) WHERE c.constructor_id IS NULL',
            'duplicate_results':'SELECT count(*) FROM (SELECT race_id,driver_id FROM race_results GROUP BY race_id,driver_id HAVING count(*)>1)',
            'duplicate_races':'SELECT count(*) FROM (SELECT season_year,round FROM races GROUP BY season_year,round HAVING count(*)>1)',
            'future_races_marked_completed':"SELECT count(*) FROM races WHERE is_completed=1 AND (date>date('now') OR julianday(start_at)>julianday('now'))",
            'completed_without_results':'SELECT count(*) FROM races r WHERE is_completed=1 AND NOT EXISTS(SELECT 1 FROM race_results x WHERE x.race_id=r.race_id)',
            'completed_unverified':'SELECT count(*) FROM races WHERE is_completed=1 AND coalesce(results_verified,0)=0',
            'orphan_results':'SELECT count(*) FROM race_results x LEFT JOIN races r USING(race_id) LEFT JOIN drivers d USING(driver_id) LEFT JOIN constructors c USING(constructor_id) WHERE r.race_id IS NULL OR d.driver_id IS NULL OR c.constructor_id IS NULL',
            'invalid_dates':"SELECT count(*) FROM races WHERE date IS NULL OR date(date) IS NULL OR cast(substr(date,1,4) AS INTEGER)!=season_year",
            'unverified_result_rows':"SELECT count(*) FROM race_results x JOIN races r USING(race_id) WHERE r.results_verified=0",
        }
        with engine.connect() as c:
            checks={name:c.execute(text(sql)).scalar() for name,sql in queries.items()}
            seasons=[dict(r) for r in c.execute(text('SELECT r.season_year,count(distinct r.race_id) races,count(x.result_id) results,count(distinct x.driver_id) drivers,count(distinct x.constructor_id) constructors FROM races r LEFT JOIN race_results x USING(race_id) GROUP BY r.season_year ORDER BY r.season_year')).mappings()]
            results=[dict(r) for r in c.execute(text('SELECT r.race_id,r.season_year,r.round,r.race_name,r.race_status,count(x.result_id) results FROM races r LEFT JOIN race_results x USING(race_id) GROUP BY r.race_id ORDER BY r.season_year,r.round')).mappings()]
            foreign_keys=[list(r) for r in c.execute(text('PRAGMA foreign_key_check'))]
        return {'generated_at':iso(utcnow()),'healthy':not any(checks.values()) and not foreign_keys,'seasons':seasons,'checks':checks,'results_per_race':results,'foreign_key_violations':foreign_keys}
