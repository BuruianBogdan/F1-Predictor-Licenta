"""Explicit network acquisition, then one atomic transaction per season."""
from collections import defaultdict
from datetime import date, timedelta
from threading import Lock
from database.db import SessionLocal
from data_sources.jolpica_provider import JolpicaProvider
from data_sources.base_provider import ProviderError
from models.driver import Driver
from models.constructor import Constructor
from models.circuit import Circuit
from models.race import Race
from models.race_result import RaceResult
from models.analytics import RaceEntry, QualifyingResult, SprintResult, StandingSnapshot, DataSyncRun
from services.season_service import utcnow, iso, parse_time, race_start

def integer(value): return int(value) if value not in (None,'') else None
def timestamp(data):
    if not data or not data.get('date'): return None
    return iso(parse_time(data['date']+'T'+data.get('time','00:00:00Z')))

class F1DataSyncService:
    _lock = Lock()
    def __init__(self, provider=None): self.provider = provider or JolpicaProvider()
    def sync_current_season(self):
        schedule = self.provider.fetch_races('current')
        if not schedule: raise ProviderError('Current calendar is empty; local data preserved')
        return self.sync_season(max(int(r['season']) for r in schedule), schedule=schedule)

    def sync_season(self, year, schedule=None):
        year = int(year)
        if not 1950 <= year <= utcnow().year+1: raise ValueError('Season must be between 1950 and next year')
        if not self._lock.acquire(blocking=False): raise ValueError('A data synchronization is already running')
        summary = defaultdict(int, season=year, started_at=iso(utcnow()), errors=[])
        for entity in ('drivers','constructors','circuits','races','results','entries','qualifying','sprints','standings'):
            for op in ('inserted','updated'): summary[f'{entity}_{op}']=0
        with SessionLocal.begin() as s:
            run = DataSyncRun(season=year, started_at=summary['started_at'], status='RUNNING', summary=dict(summary));s.add(run);s.flush();run_id=run.id
        try:
            schedule = schedule if schedule is not None else self.provider.fetch_races(year)
            if not schedule: raise ProviderError('Calendar is empty; refusing to overwrite local data')
            payloads = {'results':self.provider.fetch_results(year),'qualifying':self.provider.fetch_qualifying(year),'sprints':self.provider.fetch_sprints(year)}
            standings = {kind:self.provider.fetch_standings(year,kind) for kind in ('drivers','constructors')}
            with SessionLocal.begin() as s:
                def upsert(model, key, values, label):
                    obj = s.query(model).filter_by(**key).first()
                    if obj is None:
                        obj = model(**key, **values); s.add(obj); s.flush(); summary[label+'_inserted']+=1
                    elif any(getattr(obj,k)!=v for k,v in values.items()):
                        for k,v in values.items(): setattr(obj,k,v)
                        summary[label+'_updated']+=1
                    return obj
                def driver(d):
                    return upsert(Driver, {'driver_ref':d['driverId']}, {'number':integer(d.get('permanentNumber')), 'code':d.get('code'),'forename':d.get('givenName'),'surname':d.get('familyName'),'dob':date.fromisoformat(d['dateOfBirth']) if d.get('dateOfBirth') else None,'nationality':d.get('nationality')}, 'drivers')
                def constructor(c):
                    return upsert(Constructor, {'constructor_ref':c['constructorId']},{'name':c['name'],'nationality':c.get('nationality')},'constructors')
                race_map={}
                for raw in schedule:
                    c=raw['Circuit'];loc=c.get('Location',{})
                    circuit=upsert(Circuit,{'circuit_ref':c['circuitId']},{'name':c['circuitName'],'location':loc.get('locality'),'country':loc.get('country'),'lat':float(loc['lat']) if loc.get('lat') else None,'lng':float(loc['long']) if loc.get('long') else None},'circuits')
                    race=upsert(Race,{'season_year':year,'round':int(raw['round'])},{'circuit_id':circuit.circuit_id,'race_name':raw['raceName'],'date':date.fromisoformat(raw['date']),'start_at':timestamp(raw),'weekend_at':timestamp(raw.get('FirstPractice')),'qualifying_at':timestamp(raw.get('Qualifying')),'sprint_at':timestamp(raw.get('Sprint')),'source':self.provider.name},'races')
                    if race.race_status=='POSTPONED':
                        race.race_status='SCHEDULED'
                        summary['races_updated']+=1
                    race_map[race.round]=race
                # Missing events need review; do not silently declare cancellations or remove history.
                for old in s.query(Race).filter(Race.season_year==year).all():
                    if old.round not in race_map and not old.is_completed:
                        old.race_status='POSTPONED'
                for label,key,model in [('results','Results',RaceResult),('qualifying','QualifyingResults',QualifyingResult),('sprints','SprintResults',SprintResult)]:
                    for raw in payloads[label]:
                        race=race_map.get(int(raw['round']))
                        if race is None: raise ProviderError('Result references an absent calendar round')
                        rows=raw.get(key,[])
                        if label=='results' and rows:
                            ids=[r['Driver']['driverId'] for r in rows]
                            positions=[integer(r.get('position')) for r in rows]
                            if len(ids)!=len(set(ids)) or positions.count(1)!=1 or len(rows)<10 or any(p is None or p<1 for p in positions):
                                raise ProviderError('Incomplete/ambiguous race classification; season rolled back')
                            if race_start(race)>utcnow(): raise ProviderError('Provider returned future race results')
                        for raw_result in rows:
                            d=driver(raw_result['Driver']);c=constructor(raw_result['Constructor'])
                            # Roster reconstruction is stored separately from outcome labels.
                            upsert(RaceEntry,{'race_id':race.race_id,'driver_id':d.driver_id},{'constructor_id':c.constructor_id,'source':self.provider.name},'entries')
                            values={}
                            if label=='results':
                                fastest=raw_result.get('FastestLap',{}).get('Time',{}).get('time')
                                values={'constructor_id':c.constructor_id,'grid':integer(raw_result.get('grid')),'position':integer(raw_result.get('position')),'points':float(raw_result.get('points',0)),'status':raw_result.get('status'),'laps':integer(raw_result.get('laps')),'race_time':raw_result.get('Time',{}).get('time'),'fastest_lap':fastest,'source':self.provider.name}
                            elif label=='qualifying':
                                available = (parse_time(race.qualifying_at)+timedelta(hours=3)) if race.qualifying_at else race_start(race)-timedelta(hours=12)
                                if available > utcnow(): raise ProviderError('Future qualifying result')
                                values={'position':integer(raw_result.get('position')),'q1':raw_result.get('Q1'),'q2':raw_result.get('Q2'),'q3':raw_result.get('Q3'),'available_at':iso(available),'source':self.provider.name}
                            else:
                                available = (parse_time(race.sprint_at)+timedelta(hours=3)) if race.sprint_at else race_start(race)-timedelta(hours=12)
                                if available > utcnow(): raise ProviderError('Future sprint result')
                                values={'constructor_id':c.constructor_id,'position':integer(raw_result.get('position')),'points':float(raw_result.get('points',0)),'available_at':iso(available)}
                            upsert(model,{'race_id':race.race_id,'driver_id':d.driver_id},values,label)
                        if label=='results' and rows:
                            race.is_completed=1;race.results_verified=1;race.race_status='COMPLETED'
                for race in race_map.values():
                    if not race.results_verified or race_start(race)>utcnow():
                        race.is_completed=0
                        if race.race_status not in ('CANCELLED','POSTPONED'): race.race_status='SCHEDULED'
                for kind,lists in standings.items():
                    if not lists: continue
                    latest=max(lists,key=lambda r:int(r['round']))
                    for row in latest.get('DriverStandings',[]):
                        driver(row['Driver'])
                        for c in row.get('Constructors',[]): constructor(c)
                    for row in latest.get('ConstructorStandings',[]): constructor(row['Constructor'])
                    upsert(StandingSnapshot,{'season':year,'kind':kind},{'round':int(latest['round']),'data':latest,'updated_at':summary['started_at']},'standings')
                summary['completed_at']=iso(utcnow());summary['status']='SUCCESS'
                run=s.get(DataSyncRun,run_id);run.status='SUCCESS';run.completed_at=summary['completed_at'];run.summary=dict(summary)
            return dict(summary)
        except Exception as exc:
            summary['errors'].append(str(exc));summary['status']='FAILED';summary['completed_at']=iso(utcnow())
            with SessionLocal.begin() as s:
                run=s.get(DataSyncRun,run_id);run.status='FAILED';run.completed_at=summary['completed_at'];run.summary=dict(summary)
            raise
        finally:
            self._lock.release()
