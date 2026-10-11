"""Manual refresh of published session data; all inference inputs are versioned."""
import hashlib,json,threading
from database.db import SessionLocal
from models.race import Race
from models.circuit import Circuit
from models.analytics import SprintResult,QualifyingResult
from models.weekend import WeekendState,WeekendSessionSnapshot
from ml.feature_engineering import FeatureEngineeringService
from services.season_service import utcnow,iso,parse_time,race_start
from data_sources.weekend_provider import OfficialWeekendProvider

class WeekendService:
    lock=threading.Lock()
    def status(self,race_id):
        with SessionLocal() as s:
            race=s.get(Race,race_id)
            if not race:raise ValueError('Race not found')
            state=s.get(WeekendState,race_id)
        sessions=self.observations(race_id,utcnow())
        schedule=state.schedule if state and state.schedule else None
        data=[]
        for item in (schedule or {}).get('sessions',[]):
            observation=next((x for x in sessions if x['session']==item['code']),None)
            future=parse_time(item['start_at'])>utcnow();finished=parse_time(item['end_at'])<=utcnow()
            rows=observation['rows'] if observation else []
            leader=next((r for r in rows if r['position']==1),None)
            data.append({**item,'status':'available' if observation else ('scheduled' if future else ('awaiting_publication' if finished else 'in_progress')),'observed_at':observation['observed_at'] if observation else None,'source_url':observation['source_url'] if observation else None,'leader':leader,'rows':rows,'snapshot_id':observation['id'] if observation else None})
        forecasts=state.forecasts if state and state.forecasts else None
        if forecasts:
            import copy
            forecasts=copy.deepcopy(forecasts)
            for key in ('race','sprint'):
                if forecasts.get(key):forecasts[key]['event_started']=parse_time(forecasts[key]['event_start_at'])<=utcnow()
        return {'race_id':race_id,'race_name':race.race_name,'sprint_available':bool(race.sprint_at or any(x['code']=='SPRINT' for x in data)),'refresh_allowed':race.race_status=='SCHEDULED' and race_start(race)>utcnow(),'status':state.status if state else 'NOT_REFRESHED','last_checked_at':state.last_checked_at if state else None,'last_success_at':state.last_success_at if state else None,'details':state.details if state else None,'sessions':data,'schedule':schedule,'forecasts':forecasts,'note':'Refreshes published results after each session. In-session telemetry is not used.'}
    def observations(self,race_id,as_of):
        with SessionLocal() as s:records=s.query(WeekendSessionSnapshot).filter_by(race_id=race_id).order_by(WeekendSessionSnapshot.id.desc()).all()
        latest={}
        for r in records:
            if r.session in latest or parse_time(r.observed_at)>as_of or parse_time(r.session_end_at)>as_of:continue
            latest[r.session]={'id':r.id,'session':r.session,'start_at':r.session_start_at,'end_at':r.session_end_at,'observed_at':r.observed_at,'source_url':r.source_url,'source':r.source,'rows':r.data}
        return list(latest.values())
    def refresh(self,race_id,provider=None,calculate=True,force=False):
        if not self.lock.acquire(blocking=False):raise ValueError('A weekend refresh is already running')
        try:return self._refresh(race_id,provider or OfficialWeekendProvider(),calculate,force)
        finally:self.lock.release()
    def _refresh(self,race_id,provider,calculate,force=False):
        now=utcnow()
        with SessionLocal() as s:
            race=s.get(Race,race_id)
            if not race:raise ValueError('Race not found')
            circuit=s.get(Circuit,race.circuit_id);state=s.get(WeekendState,race_id)
            previous=state.forecasts if state and state.forecasts else {}
            if race.race_status!='SCHEDULED' or race_start(race)<=now:raise ValueError('Update weekend is available before the Grand Prix starts; historical inputs remain frozen')
            if not force and state and (not calculate or state.forecasts) and state.last_checked_at and state.status in ('SUCCESS','PARTIAL') and (now-parse_time(state.last_checked_at)).total_seconds()<30:return {'cached':True,**self.status(race_id)}
        frame=FeatureEngineeringService().build(race_id);field=frame['rows'];identities={r['driver_code']:r for r in field}
        with SessionLocal.begin() as s:
            state=s.get(WeekendState,race_id) or WeekendState(race_id=race_id);state.status='RUNNING';state.last_checked_at=iso(now);s.add(state)
        summary={'updated_sessions':[],'unchanged_sessions':[],'errors':[],'waiting':[]}
        try:
            fetched=provider.fetch(race,circuit,now)
            schedule=fetched['schedule'];summary['waiting']=fetched['waiting'];summary['errors']=fetched['errors']
            for item in fetched['sessions']:
                if parse_time(item['end_at'])>utcnow():continue
                rows=[]
                for raw in item['rows']:
                    known=identities.get(raw['driver_code'])
                    if known:rows.append({**raw,'driver_id':known['driver_id'],'constructor_id':known['constructor_id'],'driver_name':known['driver_name'],'constructor_name':known['constructor_name']})
                if len(rows)<max(2,int(.9*len(field))):
                    summary['errors'].append({'session':item['code'],'message':'Classification is incomplete or driver identities do not match the known field'});continue
                content_hash=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest();observed=iso(utcnow())
                with SessionLocal.begin() as s:
                    last=s.query(WeekendSessionSnapshot).filter_by(race_id=race_id,session=item['code']).order_by(WeekendSessionSnapshot.id.desc()).first()
                    if last and last.content_hash==content_hash:summary['unchanged_sessions'].append(item['code']);continue
                    record=WeekendSessionSnapshot(race_id=race_id,session=item['code'],source_url=item['source_url'],source=item['source'],session_start_at=item['start_at'],session_end_at=item['end_at'],observed_at=observed,content_hash=content_hash,data=rows);s.add(record)
                    if item['code']=='SPRINT':
                        for row in rows:
                            if row['points'] is None:raise ValueError('Sprint points must come from the official classification')
                            result=s.query(SprintResult).filter_by(race_id=race_id,driver_id=row['driver_id']).first() or SprintResult(race_id=race_id,driver_id=row['driver_id'])
                            result.constructor_id=row['constructor_id'];result.position=row['position'];result.points=row['points'];result.available_at=observed;s.add(result)
                    if item['code']=='Q':
                        for row in rows:
                            result=s.query(QualifyingResult).filter_by(race_id=race_id,driver_id=row['driver_id']).first() or QualifyingResult(race_id=race_id,driver_id=row['driver_id'])
                            result.position=row['position'];result.available_at=observed;result.source='formula1_official'
                            for k in ('q1','q2','q3'):setattr(result,k,row.get('segments',{}).get(k))
                            s.add(result)
                summary['updated_sessions'].append(item['code'])
            with SessionLocal.begin() as s:
                state=s.get(WeekendState,race_id);state.schedule=schedule;state.last_success_at=iso(utcnow());state.details=summary;state.status='PARTIAL' if summary['errors'] else 'SUCCESS'
                actual=s.get(Race,race_id)
                for item in schedule['sessions']:
                    attr={'FP1':'weekend_at','SPRINT':'sprint_at','Q':'qualifying_at','R':'start_at'}.get(item['code'])
                    if attr:setattr(actual,attr,item['start_at'])
            if calculate:
                from services.live_prediction_service import LivePredictionService
                from services.prediction_service import PredictionService
                live=LivePredictionService();forecasts={}
                forecasts['race']=live.predict(race_id,'RACE',persist=True)
                if any(x['code']=='SPRINT' and parse_time(x['start_at'])>utcnow() for x in schedule['sessions']):forecasts['sprint']=live.predict(race_id,'SPRINT',persist=True)
                forecasts['championship']=PredictionService().championship(race.season_year)
                for key in ('race','sprint'):
                    if key not in forecasts:continue
                    old={p['driver_id']:p['win_probability'] for p in previous.get(key,{}).get('predictions',[])}
                    for p in forecasts[key]['predictions']:
                        p['previous_win_probability']=old.get(p['driver_id']);p['probability_change']=(p['win_probability']-old[p['driver_id']])*100 if p['driver_id'] in old else None
                with SessionLocal.begin() as s:s.get(WeekendState,race_id).forecasts=forecasts
        except Exception as exc:
            with SessionLocal.begin() as s:
                state=s.get(WeekendState,race_id);state.status='FAILED';state.details={**summary,'error':str(exc)}
            raise
        return self.status(race_id)
