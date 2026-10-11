from datetime import date
from sqlalchemy import Date
from database.db import SessionLocal
from models.race import Race
from models.race_result import RaceResult

class Repository:
    def __init__(self,model,key):self.model=model;self.key=key
    def all(self):
        with SessionLocal() as s:return s.query(self.model).all()
    def get(self,entity_id):
        with SessionLocal() as s:return s.get(self.model,entity_id)
    def save(self,data,entity_id=None):
        if not isinstance(data,dict):raise ValueError('JSON object required')
        protected={'result_id','race_id' if self.model is Race else self.key,'results_verified','source'}
        with SessionLocal.begin() as s:
            item=s.get(self.model,entity_id) if entity_id is not None else self.model()
            if item is None:return None
            if entity_id is None:s.add(item)
            for key,value in data.items():
                if key in protected or key not in self.model.__table__.columns:continue
                if isinstance(self.model.__table__.columns[key].type,Date) and isinstance(value,str):value=date.fromisoformat(value) if value else None
                setattr(item,key,value)
            if self.model is Race:
                if item.race_status not in (None,'SCHEDULED','COMPLETED','POSTPONED','CANCELLED'):raise ValueError('Unknown race status')
                item.is_completed=0;item.results_verified=0
                if item.race_status in (None,'COMPLETED'):item.race_status='SCHEDULED'
                if item.date is None or item.round is None or item.round<1:raise ValueError('Race needs a valid date and round')
                if item.date.year!=item.season_year:raise ValueError('Race date must belong to its season')
            if self.model is RaceResult:
                for field in ('grid','position','points'):
                    value=getattr(item,field)
                    if value is not None and float(value)<0:raise ValueError(f'{field} cannot be negative')
                race=s.get(Race,item.race_id)
                if race:race.is_completed=0;race.results_verified=0;race.race_status='SCHEDULED'
            s.flush()
        return item
    def delete(self,entity_id):
        with SessionLocal.begin() as s:
            item=s.get(self.model,entity_id)
            if not item:return False
            if self.model is RaceResult:
                race=s.get(Race,item.race_id)
                if race:race.results_verified=0;race.is_completed=0;race.race_status='SCHEDULED'
            s.delete(item)
        return True
