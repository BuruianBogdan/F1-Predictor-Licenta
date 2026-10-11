from collections import Counter,defaultdict
import numpy as np
from database.db import SessionLocal
from models.race import Race
from models.race_result import RaceResult
from models.analytics import SprintResult
from models.driver import Driver
from config import CHAMPIONSHIP_SIMULATIONS,RANDOM_SEED
from services.season_service import SeasonContext,utcnow,race_start,parse_time,iso
from services.standings_service import StandingsService
from ml.feature_engineering import FeatureEngineeringService

POINTS=np.array([25,18,15,12,10,8,6,4,2,1])
class ChampionshipSimulationService:
    def simulate(self,season=None,simulations=None,seed=None):
        from services.prediction_service import PredictionService
        season=season or SeasonContext().get()['active_season'];n=simulations or CHAMPIONSHIP_SIMULATIONS
        if not 100<=n<=20000:raise ValueError('Simulations must be 100–20000')
        rng=np.random.default_rng(RANDOM_SEED if seed is None else seed);now=utcnow()
        with SessionLocal() as s:
            races=s.query(Race).filter_by(season_year=season).all();identities={d.driver_id:d for d in s.query(Driver).all()}
            known_sprints={r.race_id for r in s.query(SprintResult).all() if parse_time(r.available_at)<=now}
            results=s.query(RaceResult).join(Race,Race.race_id==RaceResult.race_id).filter(Race.season_year==season,Race.results_verified==1).all()
        standings=StandingsService().get_driver_standings(season)
        remaining=sorted([r for r in races if not r.is_completed and r.race_status=='SCHEDULED' and r.date and race_start(r)>now],key=lambda r:(r.date,r.round))
        pending=[r.race_id for r in races if not r.is_completed and r.race_status=='SCHEDULED' and r.date and race_start(r)<=now]
        if pending:raise ValueError('Past rounds lack verified results. Synchronize before championship simulation.')
        if any(r.sprint_at and parse_time(r.sprint_at)<=now and r.race_id not in known_sprints for r in remaining):raise ValueError('A sprint has started but its classification is not verified yet. Update the weekend after sprint results are published before simulating the championship.')
        features=FeatureEngineeringService();forecasts=[];news_races=[];live_races=[];sprint_forecasts={}
        from services.weekend_service import WeekendService
        from services.live_prediction_service import LivePredictionService
        for race in remaining:
            if WeekendService().observations(race.race_id,now):
                forecast=LivePredictionService().predict(race.race_id,'RACE',persist=False);live_races.append(race.race_id)
                if race.sprint_at and parse_time(race.sprint_at)>now:sprint_forecasts[race.race_id]=LivePredictionService().predict(race.race_id,'SPRINT',persist=False)['predictions']
            else:forecast=PredictionService().predict_race(race.race_id,persist=False,feature_service=features)
            forecasts.append((race,forecast['predictions']))
            if forecast.get('news_factor_used'):news_races.append(race.race_id)
        ids=sorted({d['driver_id'] for d in standings}|{p['driver_id'] for _,pred in forecasts for p in pred})
        if not ids:return {'season':season,'simulations':n,'remaining_races':0,'drivers':[],'limitations':['No entry/standings data']}
        index={d:i for i,d in enumerate(ids)};current={d['driver_id']:d['points'] for d in standings}
        points=np.tile([current.get(d,0) for d in ids],(n,1)).astype(float)
        countback=np.zeros((n,len(ids),31),dtype=np.int16)
        for r in results:
            if r.driver_id in index and r.position and r.position<=30:countback[:,index[r.driver_id],r.position]+=1
        for race,preds in forecasts:
            indices=np.array([index[p['driver_id']] for p in preds])
            reliability=np.clip([p['reliability_rate']/100 for p in preds],.1,.995)
            sessions=[('race',POINTS)]
            if race.sprint_at and parse_time(race.sprint_at)>now:sessions.append(('sprint',np.arange(8,0,-1)))
            for kind,awards in sessions:
                # A Grand Prix grid penalty does not also penalize the separate sprint grid.
                sprint_weights={p['driver_id']:p['win_probability'] for p in sprint_forecasts.get(race.race_id,[])}
                weights=np.maximum([sprint_weights.get(p['driver_id'],p.get('base_model_probability',p['win_probability'])) if kind=='sprint' else p['win_probability'] for p in preds],1e-10)
                session_reliability=reliability
                if kind=='sprint':
                    sprint_reliability={p['driver_id']:p['reliability_rate']/100 for p in sprint_forecasts.get(race.race_id,[])}
                    session_reliability=np.array([sprint_reliability.get(p['driver_id'],reliability[i]**(1/3)) for i,p in enumerate(preds)])
                finished=rng.random((n,len(preds)))<session_reliability
                utility=np.log(weights)[None,:]+rng.gumbel(size=(n,len(preds)))
                utility=np.where(finished,utility,utility-100)
                order=np.argsort(-utility,axis=1);finish=np.take_along_axis(finished,order,axis=1)
                for place,value in enumerate(awards[:len(preds)]):
                    points[np.arange(n),indices[order[:,place]]]+=value*finish[:,place]
                if kind=='race':
                    for place in range(len(preds)):countback[np.arange(n),indices[order[:,place]],place+1]+=1
        # FIA-style countback on full race classifications; exactly unresolved ties split probability.
        wins=np.zeros(len(ids));position_total=np.zeros(len(ids))
        for simulation in range(n):
            keys=[(points[simulation,i],*countback[simulation,i,1:].tolist()) for i in range(len(ids))]
            order=sorted(range(len(ids)),key=lambda i:keys[i],reverse=True)
            best=keys[order[0]];tied=[i for i in order if keys[i]==best]
            wins[tied]+=1/len(tied)
            for rank,i in enumerate(order,1):position_total[i]+=rank
        drivers=[]
        for d,i in index.items():
            driver=identities[d];prob=float(wins[i]/n)
            drivers.append({'driver_id':d,'driver_name':f'{driver.forename} {driver.surname}','name':f'{driver.forename} {driver.surname}','code':driver.code,'current_points':current.get(d,0),'historical_points':current.get(d,0),'championship_probability':prob,'win_probability':prob,'expected_final_points':round(float(points[:,i].mean()),2),'expected_final_position':round(float(position_total[i]/n),2),'predicted_score':round(float(points[:,i].mean()),2)})
        drivers.sort(key=lambda p:(-p['championship_probability'],-p['expected_final_points']))
        for rank,p in enumerate(drivers,1):p['predicted_position']=rank
        return {'weekend_adjusted_races':live_races,'news_adjusted_races':news_races,'news_factor_used':bool(news_races),'news_note':'Eligible confirmed news adjusts simulated future points, never official points. Experimental assumptions; not backtested.','season':season,'simulations':n,'seed':RANDOM_SEED if seed is None else seed,'remaining_races':len(remaining),'remaining_sprints':sum(bool(r.sprint_at and parse_time(r.sprint_at)>now) for r in remaining),'drivers':drivers,'as_of':iso(now),'model_version':'monte-carlo-v2','probability_unit':'fraction','limitations':['Fixed current form for remaining races; no future development model','Independent DNF draw; retired drivers receive no simulated points, even if classified','Full points assumed; shortened races are not simulated','Sprint uses current weekend evidence when available, otherwise a Grand Prix-strength prior','Historical seasons return final known standings, not a past forecast']}
