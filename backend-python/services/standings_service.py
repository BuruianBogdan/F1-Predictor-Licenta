from collections import defaultdict, Counter
from database.db import SessionLocal
from models.driver import Driver
from models.constructor import Constructor
from models.race import Race
from models.race_result import RaceResult
from models.analytics import StandingSnapshot, SprintResult
from services.season_service import SeasonContext, utcnow

class StandingsService:
    def _get(self, kind, season=None):
        season=season or SeasonContext().get()['active_season']
        with SessionLocal() as s:
            snapshot=s.query(StandingSnapshot).filter_by(season=season,kind=kind).first()
            drivers={d.driver_ref:d for d in s.query(Driver).all()}
            teams={c.constructor_ref:c for c in s.query(Constructor).all()}
            if snapshot:
                result=[]
                for raw in snapshot.data.get('DriverStandings' if kind=='drivers' else 'ConstructorStandings',[]):
                    if kind=='drivers':
                        d=drivers.get(raw['Driver']['driverId'])
                        if not d: continue
                        item={'driver_id':d.driver_id,'driver_name':f'{d.forename} {d.surname}','code':d.code}
                    else:
                        c=teams.get(raw['Constructor']['constructorId'])
                        if not c: continue
                        item={'constructor_id':c.constructor_id,'constructor_name':c.name,'nationality':c.nationality}
                    result.append({**item,'position':int(raw['position']),'points':float(raw['points']),'wins':int(raw.get('wins',0)),'source':'jolpica','round':snapshot.round,'season':season})
                return result
            # Offline fallback is explicitly labelled, includes sprints and countback.
            races=s.query(Race).filter(Race.season_year==season,Race.results_verified==1,Race.date<=utcnow().date()).all()
            race_ids=[r.race_id for r in races]
            points=defaultdict(float); finishes=defaultdict(Counter)
            for row in s.query(RaceResult).filter(RaceResult.race_id.in_(race_ids)).all():
                entity=row.driver_id if kind=='drivers' else row.constructor_id
                points[entity]+=row.points or 0;finishes[entity][row.position or 99]+=1
            for row in s.query(SprintResult).join(Race, Race.race_id==SprintResult.race_id).filter(Race.season_year==season).all():
                entity=row.driver_id if kind=='drivers' else row.constructor_id;points[entity]+=row.points or 0
            identities={d.driver_id:d for d in drivers.values()} if kind=='drivers' else {c.constructor_id:c for c in teams.values()}
            order=sorted(points,key=lambda i:(-points[i],*[-finishes[i][p] for p in range(1,31)],i))
            out=[]
            for pos,i in enumerate(order,1):
                entity=identities[i]
                data={'driver_id':i,'driver_name':f'{entity.forename} {entity.surname}','code':entity.code} if kind=='drivers' else {'constructor_id':i,'constructor_name':entity.name,'nationality':entity.nationality}
                out.append({**data,'position':pos,'points':points[i],'wins':finishes[i][1],'source':'local_reconstruction','season':season})
            return out
    def get_driver_standings(self, season=None): return self._get('drivers',season)
    def get_constructor_standings(self, season=None): return self._get('constructors',season)
