from datetime import datetime,timezone
from services.data_sync_service import F1DataSyncService
from data_sources.fastf1_provider import FastF1Provider
from database.db import SessionLocal
from models.race import Race
from models.analytics import SessionData
from services.season_service import iso,utcnow

class FastF1Importer:
    def __init__(self,year=None): self.year=year or datetime.now(timezone.utc).year
    def import_season(self):
        summary=F1DataSyncService().sync_season(self.year)
        summary['fastf1_note']='Session enrichment is explicit via scripts/enrich_session.py; no season-wide telemetry download.'
        return summary
    def enrich_session(self,race_id,session='Q',telemetry=False,laps=False):
        with SessionLocal() as s:
            race=s.get(Race,race_id)
            if not race: raise ValueError('Race not found')
            data=FastF1Provider().fetch_session(race.season_year,race.round,session,telemetry,laps)
            row=s.query(SessionData).filter_by(race_id=race_id,session=session).first()
            if row is None: row=SessionData(race_id=race_id,session=session);s.add(row)
            row.data=data;row.source='fastf1';row.updated_at=iso(utcnow());s.commit()
            return {'race_id':race_id,'session':session,'results':len(data['results']),'weather_samples':len(data['weather']),'telemetry_loaded':telemetry}
