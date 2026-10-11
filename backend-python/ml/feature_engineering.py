"""All numeric features are computed strictly before an explicit UTC cutoff.

Target entrants are identities, never outcomes. Historical rosters are reconstructed
from provider entries; upcoming rosters are projected from the latest known field.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import numpy as np
from database.db import SessionLocal
from models.driver import Driver
from models.constructor import Constructor
from models.race import Race
from models.race_result import RaceResult
from models.analytics import RaceEntry, QualifyingResult, SprintResult
from services.season_service import utcnow, iso, parse_time, race_start

FEATURES = [
    'races_started_before_target','season_points_before_target','championship_position_before_target',
    'avg_finish_last_3','avg_finish_last_5','avg_finish_last_10',
    'points_last_3','points_last_5','points_last_10','podiums_last_5','wins_last_10',
    'finish_rate_last_10','dnf_rate_last_10','position_trend','points_trend',
    'driver_circuit_avg_finish','driver_circuit_previous_results',
    'constructor_points_before_target','constructor_championship_position',
    'constructor_avg_finish_last_3','constructor_avg_finish_last_5','constructor_points_last_5',
    'constructor_podium_rate','constructor_dnf_rate','constructor_momentum',
    'qualifying_position','qualifying_known','grid_position','grid_known',
    'round_number','regulation_era','circuit_dnf_rate',
]

def is_finished(status):
    text=(status or '').lower()
    return text=='finished' or (text.startswith('+') and 'lap' in text)
def safe_position(position,default=20): return position if position and position>0 else default
def mean(values,default=0.0): return float(np.mean(values)) if values else float(default)
def trend(values): return float(np.polyfit(np.arange(len(values)),values,1)[0]) if len(values)>1 else 0.0

class QualifyingUnavailableError(ValueError):
    code='QUALIFYING_UNAVAILABLE'

def prediction_cutoff(race,mode,now=None):
    now=now or utcnow();start=race_start(race)
    weekend=parse_time(race.weekend_at) or start-timedelta(days=2)
    return min(now,weekend if mode=='PRE_WEEKEND' else start-timedelta(seconds=1))

class FeatureEngineeringService:
    def __init__(self):
        with SessionLocal() as s:
            self.races={r.race_id:r for r in s.query(Race).all()}
            self.drivers={d.driver_id:d for d in s.query(Driver).all()}
            self.constructors={c.constructor_id:c for c in s.query(Constructor).all()}
            self.results=s.query(RaceResult).all()
            self.entries=s.query(RaceEntry).all()
            self.qualifying=s.query(QualifyingResult).all()
            self.sprints=s.query(SprintResult).all()
        self.entries_by_race=defaultdict(list)
        for e in self.entries:self.entries_by_race[e.race_id].append(e)
        self.results.sort(key=lambda r:(self.races[r.race_id].date,self.races[r.race_id].round,r.driver_id))

    def build(self, race_id, mode='PRE_WEEKEND', as_of=None):
        mode=mode.upper()
        if mode not in ('PRE_WEEKEND','POST_PRACTICE','POST_QUALIFYING'):raise ValueError('Unknown prediction mode')
        race=self.races.get(race_id)
        if not race or not race.date:raise ValueError('Race not found or has no scheduled date')
        if race.race_status in ('CANCELLED','POSTPONED'):raise ValueError('Race is not scheduled')
        cutoff=prediction_cutoff(race,mode,as_of)
        # A six-hour finalization buffer prevents same-day/session overlap.
        historical=[r for r in self.results if r.race_id!=race_id and self.races[r.race_id].results_verified and race_start(self.races[r.race_id])+timedelta(hours=6)<cutoff]
        field=self.entries_by_race.get(race_id,[])
        roster_source='reconstructed_target_entry_list' if field else 'projected_latest_field'
        if not field:
            previous=[r for r in self.races.values() if r.date and race_start(r)<cutoff and self.entries_by_race.get(r.race_id)]
            if previous:
                last=max(previous,key=lambda r:(r.date,r.round));field=self.entries_by_race[last.race_id]
        if not field: raise ValueError('No known driver entry list; synchronize race/qualifying data first')
        by_driver=defaultdict(list);by_constructor=defaultdict(list);driver_points=defaultdict(float);team_points=defaultdict(float)
        for result in historical:
            by_driver[result.driver_id].append(result);by_constructor[result.constructor_id].append(result)
            if self.races[result.race_id].season_year==race.season_year:
                driver_points[result.driver_id]+=result.points or 0;team_points[result.constructor_id]+=result.points or 0
        for result in self.sprints:
            if self.races[result.race_id].season_year==race.season_year and parse_time(result.available_at)<cutoff:
                driver_points[result.driver_id]+=result.points or 0;team_points[result.constructor_id]+=result.points or 0
        def rank(points,entity):return 1+sum(v>points[entity] for v in points.values())
        qualifying={q.driver_id:q for q in self.qualifying if q.race_id==race_id and parse_time(q.available_at)<cutoff} if mode=='POST_QUALIFYING' else {}
        if mode=='POST_QUALIFYING' and not qualifying:raise QualifyingUnavailableError('Qualifying results are not available for this prediction yet. Use Pre-weekend, or synchronize after qualifying.')
        circuit_results=[r for r in historical if self.races[r.race_id].circuit_id==race.circuit_id]
        output=[]
        for entry in sorted(field,key=lambda e:e.driver_id):
            d=self.drivers[entry.driver_id];team=self.constructors[entry.constructor_id]
            history=by_driver[d.driver_id];recent=history[-10:];teams=by_constructor[entry.constructor_id]
            team_race_ids=[]
            for r in reversed(teams):
                if r.race_id not in team_race_ids:team_race_ids.append(r.race_id)
            t3=[r for r in teams if r.race_id in team_race_ids[:3]];t5=[r for r in teams if r.race_id in team_race_ids[:5]]
            circuit=[r for r in history if self.races[r.race_id].circuit_id==race.circuit_id]
            f={'races_started_before_target':len(history),'season_points_before_target':driver_points[d.driver_id],
               'championship_position_before_target':rank(driver_points,d.driver_id),'podiums_last_5':sum(safe_position(r.position)<=3 for r in history[-5:]),'wins_last_10':sum(r.position==1 for r in recent),
               'finish_rate_last_10':mean([is_finished(r.status) for r in recent],0.85),'dnf_rate_last_10':mean([not is_finished(r.status) for r in recent],0.15),
               'position_trend':-trend([safe_position(r.position) for r in history[-5:]]),'points_trend':trend([r.points or 0 for r in history[-5:]]),
               'driver_circuit_avg_finish':mean([safe_position(r.position) for r in circuit],12),'driver_circuit_previous_results':len(circuit),
               'constructor_points_before_target':team_points[entry.constructor_id],'constructor_championship_position':rank(team_points,entry.constructor_id),
               'constructor_avg_finish_last_3':mean([safe_position(r.position) for r in t3],12),'constructor_avg_finish_last_5':mean([safe_position(r.position) for r in t5],12),
               'constructor_points_last_5':sum(r.points or 0 for r in t5),'constructor_podium_rate':mean([safe_position(r.position)<=3 for r in t5]),
               'constructor_dnf_rate':mean([not is_finished(r.status) for r in t5],0.15),'constructor_momentum':mean([r.points or 0 for r in t3])-mean([r.points or 0 for r in t5]),
               'qualifying_position':qualifying[d.driver_id].position if d.driver_id in qualifying else 0,'qualifying_known':int(d.driver_id in qualifying),
               # Final starting grid from race results is deliberately never used.
               'grid_position':0,'grid_known':0,'round_number':race.round,'regulation_era':2026 if race.season_year>=2026 else (2022 if race.season_year>=2022 else 2014),
               'circuit_dnf_rate':mean([not is_finished(r.status) for r in circuit_results],0.15)}
            for window in (3,5,10):
                f[f'avg_finish_last_{window}']=mean([safe_position(r.position) for r in history[-window:]],12)
                f[f'points_last_{window}']=sum(r.points or 0 for r in history[-window:])
            output.append({'driver_id':d.driver_id,'driver_name':f'{d.forename} {d.surname}','driver_code':d.code,'driver_ref':d.driver_ref,'constructor_id':team.constructor_id,'constructor_name':team.name,'constructor_ref':team.constructor_ref,'features':f})
        return {'race':race.to_dict(),'mode':mode,'feature_cutoff':iso(cutoff),'roster_source':roster_source,'rows':output,'practice_features_available':False,'grid_available':False}

    def dataset(self, mode='PRE_WEEKEND'):
        import pandas as pd
        result_map={(r.race_id,r.driver_id):r for r in self.results}
        rows=[]
        for race in sorted(self.races.values(),key=lambda r:(r.date or datetime.min.date(),r.round)):
            if not race.results_verified or not race.is_completed:continue
            if len(self.entries_by_race[race.race_id])<10:continue
            try:frame=self.build(race.race_id,mode)
            except ValueError:continue
            for row in frame['rows']:
                actual=result_map.get((race.race_id,row['driver_id']))
                if not actual or not actual.position:continue
                rows.append({**row['features'],'race_id':race.race_id,'driver_id':row['driver_id'],'season':race.season_year,'date':str(race.date),'feature_cutoff':frame['feature_cutoff'],
                             'winner':int(actual.position==1),'podium':int(actual.position<=3),'points_finish':int(actual.position<=10),'position':actual.position})
        return pd.DataFrame(rows)
