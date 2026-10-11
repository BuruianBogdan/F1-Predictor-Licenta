from collections import defaultdict
from statistics import mean
from sqlalchemy import func
from database.db import SessionLocal
from models.race import Race
from models.race_result import RaceResult
from models.driver import Driver
from models.constructor import Constructor
from models.circuit import Circuit
from models.analytics import PredictionRun,SessionData
from services.season_service import SeasonContext,race_start,utcnow,parse_time
from services.media_service import MediaService
from services.circuit_service import CircuitPresentationService
from services.standings_service import StandingsService
from ml.feature_engineering import is_finished

class InsightService:
    def race_detail(self,race_id):
        with SessionLocal() as s:
            race=s.get(Race,race_id)
            if not race:raise ValueError('Race not found')
            circuit=s.get(Circuit,race.circuit_id)
            rows=s.query(RaceResult,Driver,Constructor).join(Driver,Driver.driver_id==RaceResult.driver_id).join(Constructor,Constructor.constructor_id==RaceResult.constructor_id).filter(RaceResult.race_id==race_id).order_by(RaceResult.position).all()
            results=[]
            if race.results_verified and race_start(race)<=utcnow():
                for result,d,team in rows:
                    results.append({**result.to_dict(),'driver_name':f'{d.forename} {d.surname}','driver_code':d.code,'driver_number':d.number,'constructor_name':team.name,**MediaService().get(d.driver_id,team.constructor_ref)})
            runs=s.query(PredictionRun).filter_by(race_id=race_id,replay=0).order_by(PredictionRun.created_at.desc()).all()
            valid=[r for r in runs if r.kind in ('race','race_market','live_race') and parse_time(r.created_at)<race_start(race)]
            pre=valid[0] if valid else None
            session=s.query(SessionData).filter_by(race_id=race_id,session='R').first()
            weather=session.data.get('weather',[]) if session else []
        winner=next((r for r in results if r['position']==1),None)
        review=None
        if pre and results:
            actual={r['driver_id']:r['position'] for r in results};top=sorted(pre.predictions,key=lambda p:p['predicted_position'])
            review={'run_id':pre.id,'model_version':pre.model_version,'created_at':pre.created_at,'top1_hit':actual.get(top[0]['driver_id'])==1,'top3_hit':sum(actual.get(p['driver_id'],99)<=3 for p in top[:3]),'predicted_winner':top[0]['driver_name'],'actual_winner':winner['driver_name'] if winner else None}
        circuit_data=CircuitPresentationService().present(circuit)
        return {'race':{**race.to_dict(),'circuit':circuit_data},'circuit':circuit_data,'winner':winner,'podium':results[:3],'results':results,'weather':weather,'prediction_review':review,'prediction_review_note':'No genuine pre-race prediction was recorded' if not review else None}

    def driver_detail(self,driver_id):
        context=SeasonContext().get();season=context['active_season']
        with SessionLocal() as s:
            driver=s.get(Driver,driver_id)
            if not driver:raise ValueError('Driver not found')
            rows=s.query(RaceResult,Race,Constructor,Circuit).join(Race,Race.race_id==RaceResult.race_id).join(Constructor,Constructor.constructor_id==RaceResult.constructor_id).join(Circuit,Circuit.circuit_id==Race.circuit_id).filter(RaceResult.driver_id==driver_id,Race.results_verified==1).order_by(Race.date.desc()).all()
        recent=[{**r.to_dict(),'race_name':race.race_name,'date':str(race.date),'season':race.season_year,'constructor_name':team.name,'circuit':circuit.name} for r,race,team,circuit in rows]
        current=[r for r in recent if r['season']==season];standing=next((r for r in StandingsService().get_driver_standings(season) if r['driver_id']==driver_id),{})
        circuit_positions=defaultdict(list)
        for r in recent:
            if r['position']:circuit_positions[r['circuit']].append(r['position'])
        strengths=sorted([{'circuit':k,'average_finish':round(mean(v),2),'starts':len(v)} for k,v in circuit_positions.items()],key=lambda r:r['average_finish'])[:5]
        team=rows[0][2] if rows else None;next_prediction=None
        if context['next_race']:
            from services.prediction_service import PredictionService
            next_prediction=next((p for p in PredictionService().latest_forecast(context['next_race']['race_id'])['predictions'] if p['driver_id']==driver_id),None)
        return {'driver':{**driver.to_dict(),'driver_name':f'{driver.forename} {driver.surname}'},'season':season,'constructor':team.name if team else None,'standing':standing,'wins':sum(r['position']==1 for r in current),'podiums':sum(r['position'] and r['position']<=3 for r in current),'dnf_rate':sum(not is_finished(r['status']) for r in current)/len(current) if current else None,'recent_results':recent[:5],'form_chart':list(reversed(recent[:10])),'circuit_strengths':strengths,'next_prediction':next_prediction,**MediaService().get(driver_id,team.constructor_ref if team else None)}
