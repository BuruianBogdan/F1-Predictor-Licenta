"""Explicit weekend evidence mixture. Learned baseline metrics do not validate this overlay."""
import copy
import numpy as np
from database.db import SessionLocal
from models.race import Race
from services.season_service import utcnow,parse_time,iso,race_start
from services.weekend_service import WeekendService
from ml.feature_engineering import FeatureEngineeringService
from services.news_impact_service import NewsImpactService

class SprintUnavailableError(ValueError):code='SPRINT_UNAVAILABLE'
class EventStartedError(ValueError):code='EVENT_STARTED'

class LivePredictionService:
    def predict(self,race_id,target='RACE',persist=True,as_of=None,pre_weekend=False):
        from services.prediction_service import PredictionService
        target=target.upper()
        if target not in ('RACE','SPRINT'):raise ValueError('Choose Grand Prix or Sprint')
        with SessionLocal() as s:race=s.get(Race,race_id)
        if not race:raise ValueError('Race not found')
        now=min(as_of or utcnow(),utcnow());start=race_start(race) if target=='RACE' else parse_time(race.sprint_at)
        if not start:raise SprintUnavailableError('This weekend has no scheduled sprint')
        if now>=start:raise EventStartedError('This event has started; a new pre-event forecast cannot be created. Inspect the saved forecast and published classification.')
        base=PredictionService().predict_race(race_id,'PRE_WEEKEND',persist=False,as_of=now)
        frame=FeatureEngineeringService().build(race_id,'PRE_WEEKEND',as_of=now)
        cutoff=min(now,start)
        if pre_weekend:cutoff=min(cutoff,parse_time(frame['feature_cutoff']))
        snapshots=WeekendService().observations(race_id,cutoff)
        allowed={'FP1','FP2','FP3','SQ','SPRINT_GRID'} if target=='SPRINT' else {'FP1','FP2','FP3','SQ','SPRINT','Q','RACE_GRID'}
        snapshots=[x for x in snapshots if x['session'] in allowed and parse_time(x['end_at'])<start]
        latest={x['session']:x for x in snapshots}
        preds=sorted(copy.deepcopy(base['predictions']),key=lambda p:p['driver_id']);ids=[p['driver_id'] for p in preds];n=len(ids)
        prior=np.array([p['base_model_probability'] for p in preds]);components=[];evidence={d:[] for d in ids}
        def component(snapshot,weight,beta,practice=False):
            valid={r['driver_id']:r for r in snapshot['rows'] if r['driver_id'] in ids and r['position'] and (not practice or r.get('best_lap_seconds') is not None)}
            if len(valid)<max(2,int(.5*n)):return None
            strength=np.zeros(n)
            # Only compare within a session; never compare FP1 and FP2 absolute times.
            if practice:
                fastest=min(r['best_lap_seconds'] for r in valid.values())
                raw=np.array([np.exp(-min(5,valid[d]['best_lap_seconds']-fastest)/.8) if d in valid else 0 for d in ids])
            else:raw=np.array([np.exp(-beta*(valid[d]['position']-1)) if d in valid else 0 for d in ids])
            # Missing observations retain their prior mass instead of becoming zero chance.
            observed_mass=sum(prior[i] for i,d in enumerate(ids) if d in valid)
            distribution=prior.copy();known=[i for i,d in enumerate(ids) if d in valid]
            distribution[known]=raw[known]/raw[known].sum()*observed_mass
            for d,row in valid.items():evidence[d].append({'session':snapshot['session'],'position':row['position'],'time_text':row.get('time_text'),'best_lap_seconds':row.get('best_lap_seconds'),'source_url':snapshot['source_url'],'snapshot_id':snapshot['id'],'observed_at':snapshot['observed_at']})
            return {'weight':weight,'distribution':distribution,'session':snapshot['session'],'snapshot_id':snapshot['id']}
        practice=[]
        for code in ('FP1','FP2','FP3'):
            if code in latest:
                c=component(latest[code],{'FP1':1,'FP2':2,'FP3':3}[code],.1,True)
                if c:practice.append(c)
        if practice:
            total=sum(c['weight'] for c in practice);components.append({'weight':.10,'distribution':sum(c['weight']*c['distribution'] for c in practice)/total,'session':'PRACTICE','snapshot_ids':[c['snapshot_id'] for c in practice]})
        if target=='SPRINT':
            grid=latest.get('SPRINT_GRID') or latest.get('SQ')
            if grid:
                c=component(grid,.72,.18)
                if c:components.append(c)
        else:
            grid=latest.get('RACE_GRID') or latest.get('Q')
            if grid:
                c=component(grid,.62 if grid['session']=='Q' else .67,.14)
                if c:components.append(c)
            if 'SQ' in latest:
                c=component(latest['SQ'],.12,.14)
                if c:components.append(c)
            if 'SPRINT' in latest:
                c=component(latest['SPRINT'],.12,.12)
                if c:components.append(c)
        total=sum(c['weight'] for c in components)
        if total>.85:
            for c in components:c['weight']*=.85/total
            total=.85
        session_distribution=(1-total)*prior+sum((c['weight']*c['distribution'] for c in components),np.zeros(n))
        frame['feature_cutoff']=iso(cutoff);frame['rows']=sorted(frame['rows'],key=lambda r:r['driver_id'])
        news_meta={'news_factor_used':False,'news_signal_ids':[],'news_cutoff':iso(cutoff),'news_note':'Grand Prix grid-penalty news does not apply to the sprint.'}
        news_changes=[[] for _ in ids];final=session_distribution.copy()
        if target=='RACE' and 'RACE_GRID' not in latest:final,news_changes,news_meta=NewsImpactService().apply(frame,session_distribution)
        if target=='RACE' and 'RACE_GRID' in latest:news_meta['news_note']='The published Grand Prix grid already incorporates penalties; the grid penalty news adjustment is not applied again.'
        # Finish/points simulation is shared with the championship assumptions.
        rng=np.random.default_rng(42);draws=6000;reliability=np.clip([p['reliability_rate']/100 for p in preds],.1,.995)
        if target=='SPRINT':reliability=reliability**(1/3) # Assumed constant-distance retirement hazard; sprint is roughly one-third distance.
        finished=rng.random((draws,n))<reliability
        utility=np.log(np.maximum(final,1e-12))[None,:]+rng.gumbel(size=(draws,n));order=np.argsort(-np.where(finished,utility,utility-100),axis=1)
        finish_order=np.take_along_axis(finished,order,axis=1);valid=finished.any(axis=1)
        podium=np.zeros(n);points=np.zeros(n);expected=np.zeros(n);awards=np.arange(8,0,-1) if target=='SPRINT' else np.array([25,18,15,12,10,8,6,4,2,1])
        for pos in range(min(n,len(awards))):
            d=order[:,pos];ok=finish_order[:,pos]
            np.add.at(expected,d,awards[pos]*ok/draws)
            np.add.at(points,d,ok/max(1,valid.sum()))
            if pos<3:np.add.at(podium,d,ok/max(1,valid.sum()))
        for i,p in enumerate(preds):
            p.update(win_probability=float(final[i]),final_probability=float(final[i]),model_probability=float(prior[i]),base_model_probability=float(prior[i]),session_probability=float(session_distribution[i]),news_adjusted_probability=float(final[i]),news_delta=float(final[i]-session_distribution[i]),win_percentage=round(final[i]*100,2),score=float(final[i]),predicted_score=float(final[i]*100),podium_probability=max(float(final[i]),float(podium[i])),points_probability=max(float(final[i]),float(podium[i]),float(points[i])),expected_points=round(float(expected[i]),2),session_evidence=evidence[p['driver_id']],news_signals=news_changes[i])
            if target=='SPRINT':
                p['historical_gp_finish_rate']=p['reliability_rate'];p['baseline_reliability_rate']=float(np.clip(p['reliability_rate']/100,.1,.995)*100);p['reliability_rate']=float(reliability[i]*100)
                p['factors']['reliability']={'value':round(float(reliability[i]),3),'unit':'sprint finish prior, distance-scaled from historical GP finishes','impact':'assumption'}
            p['factors']['weekend_sessions']={'value':len(evidence[p['driver_id']]),'unit':'published session observations','impact':'observed'}
        preds.sort(key=lambda p:(-p['win_probability'],p['driver_id']))
        for rank,p in enumerate(preds,1):p['rank']=rank;p['predicted_position']=rank
        response={**base,**news_meta,'model_type':'weekend_evidence_mixture','baseline_model_type':base['model_type'],'model_version':base['model_version']+'+weekend-v1','confidence':{'favourite_probability':preds[0]['win_probability'],'label':'Experimental weekend probability; no certainty claim'},'target':target,'predictions':preds,'mode':'PRE_WEEKEND' if pre_weekend else 'LIVE','event_start_at':iso(start),'feature_cutoff':iso(cutoff),'base_feature_cutoff':base['feature_cutoff'],'historical_replay':False,'session_factor_used':bool(components),'session_snapshot_ids':sorted({e['snapshot_id'] for values in evidence.values() for e in values}),'session_components':[{k:v for k,v in c.items() if k!='distribution'} for c in components],'updated_at':iso(now),'live_method':'Bounded mixture of historical calibrated GP probabilities and published within-session pace/classification distributions. Sprint uses a GP prior; this weekend overlay and sprint model are experimental, not yet backtested.','points_places':8 if target=='SPRINT' else 10,'probability_unit':'fraction','limitations':['Practice fuel loads and compounds may differ; total practice weight is limited to 10%.','Sprint qualifying indicates a provisional sprint grid, not the Grand Prix grid.','Session and sprint overlays are not included in published baseline accuracy.','Points simulation assumes full-distance points and independent retirement risk; sprint finish prior uses GP reliability to the power 1/3.']}
        if persist:
            from services.history_service import HistoryService
            response['prediction_run_id']=HistoryService().record('sprint' if target=='SPRINT' else 'live_race',race_id,preds,{k:v for k,v in response.items() if k!='predictions'})
        return response
