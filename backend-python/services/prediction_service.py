import copy
import numpy as np
from ml.feature_engineering import FeatureEngineeringService
from ml.baseline import HeuristicBaselineModel
from ml.race_model import load_for_cutoff
from config import PREDICTION_MODE
from services.media_service import MediaService
from services.season_service import utcnow,parse_time,iso

class PredictionService:
    def available_modes(self,season=None):
        from database.db import SessionLocal
        from models.race import Race
        from models.analytics import QualifyingResult
        from ml.feature_engineering import prediction_cutoff
        with SessionLocal() as s:
            query=s.query(Race)
            if season is not None:query=query.filter_by(season_year=season)
            races=query.all()
            qualifying=s.query(QualifyingResult.race_id,QualifyingResult.available_at).filter(QualifyingResult.race_id.in_([r.race_id for r in races])).all()
        now=utcnow();available={}
        for race in races:
            cutoff=prediction_cutoff(race,'POST_QUALIFYING',now) if race.date else None
            ready=bool(cutoff and race.race_status not in ('CANCELLED','POSTPONED') and any(rid==race.race_id and parse_time(stamp)<cutoff for rid,stamp in qualifying))
            available[str(race.race_id)]={'post_qualifying_available':ready,'qualifying_at':race.qualifying_at,'sprint_available':bool(race.sprint_at),'live_refresh_available':bool(race.date and parse_time(race.start_at or str(race.date))>now and race.race_status=='SCHEDULED')}
        return available

    def predict_race(self,race_id,mode='PRE_WEEKEND',persist=True,scenario=None,feature_service=None,as_of=None):
        if mode.upper()=='LIVE':
            if scenario:raise ValueError('Use a baseline mode for hypothetical scenarios')
            from services.live_prediction_service import LivePredictionService
            return LivePredictionService().predict(race_id,'RACE',persist=persist,as_of=as_of)
        frame=(feature_service or FeatureEngineeringService()).build(race_id,mode,as_of=as_of)
        rows=copy.deepcopy(frame['rows'])
        if scenario:
            from services.regulation_service import RegulationService
            settings=RegulationService().get()
            for row in rows:
                if scenario.get('driver_id') is not None and row['driver_id']!=int(scenario['driver_id']):continue
                if scenario.get('constructor_id') is not None and row['constructor_id']!=int(scenario['constructor_id']):continue
                f=row['features'];pace=float(scenario.get('pace_delta') or 0)
                for key in ('avg_finish_last_3','avg_finish_last_5','constructor_avg_finish_last_3','constructor_avg_finish_last_5'):
                    f[key]=max(1,f[key]-pace*(1+settings['budget_cap_upgrade_weight'])/5)
                f['finish_rate_last_10']=float(np.clip(f['finish_rate_last_10']+(float(scenario.get('reliability_delta') or 0)-float(scenario.get('dnf_risk_delta') or 0))*(1+settings['reliability_weight'])/100,0,1))
                f['dnf_rate_last_10']=1-f['finish_rate_last_10']
                if scenario.get('grid_position'):
                    if not 1<=int(scenario['grid_position'])<=len(rows):raise ValueError('Hypothetical grid position must be within the race field')
                    f['grid_known']=1;f['grid_position']=int(scenario['grid_position'])
        model,metadata=load_for_cutoff(frame['feature_cutoff'],frame['mode'])
        if PREDICTION_MODE=='heuristic':model=None;metadata={'model_version':HeuristicBaselineModel.version,'training_cutoff':None,'reason':'Configured heuristic baseline'}
        output=(model or HeuristicBaselineModel()).predict(rows)
        if scenario:
            # Explicit sensitivity assumptions: no learned causal grid/weather model.
            for i,row in enumerate(rows):
                if row['features']['grid_known']:
                    output['win'][i]*=np.exp(.08*((len(rows)+1)/2-row['features']['grid_position']))
            output['win']/=output['win'].sum()
            uncertainty=.1*(settings['aero_rule_change_weight']+settings['safety_car_randomness'])
            if frame['race'].get('sprint_at'):uncertainty+=.1*settings['sprint_impact_weight']
            if scenario.get('wet_race'):uncertainty+=settings['wet_race_uncertainty']
            uncertainty=min(.8,uncertainty)
            output['win']=(1-uncertainty)*output['win']+uncertainty/len(rows)
        from services.news_impact_service import NewsImpactService
        base_win=output['win'].copy()
        output['win'],news_changes,news_meta=NewsImpactService().apply(frame,base_win)
        predictions=[]
        for i,row in enumerate(rows):
            f=row['features'];win=float(output['win'][i]);podium=max(win,float(output['podium'][i]));points=max(podium,float(output['points'][i]))
            factors={
                'recent_form':{'value':round(f['avg_finish_last_5'],2),'unit':'average finish, last 5','impact':'positive' if f['avg_finish_last_5']<10 else 'negative'},
                'constructor_form':{'value':round(f['constructor_avg_finish_last_5'],2),'unit':'average team finish, last 5 races','impact':'positive' if f['constructor_avg_finish_last_5']<10 else 'negative'},
                'grid':{'value':f['grid_position'] if f['grid_known'] else None,'unit':'hypothetical starting grid' if f['grid_known'] else 'starting grid not sourced','impact':'scenario' if f['grid_known'] else 'unavailable'},
                'qualifying':{'value':f['qualifying_position'] if f['qualifying_known'] else None,'unit':'qualifying position; not final grid','impact':'observed' if f['qualifying_known'] else 'unavailable'},
                'reliability':{'value':round(f['finish_rate_last_10'],3),'unit':'finish rate last 10','impact':'positive' if f['finish_rate_last_10']>=.85 else 'negative'},
                'circuit_history':{'value':round(f['driver_circuit_avg_finish'],2) if f['driver_circuit_previous_results'] else None,'unit':'prior average finish','impact':'observed' if f['driver_circuit_previous_results'] else 'unavailable'}}
            predictions.append({k:v for k,v in row.items() if k!='features'} | {'win_probability':win,'win_percentage':round(win*100,2),'podium_probability':podium,'points_probability':points,'predicted_score':win*100,'score':win,'model_probability':float(base_win[i]),'base_model_probability':float(base_win[i]),'news_adjusted_probability':win,'news_delta':win-float(base_win[i]),'news_signals':news_changes[i],'final_probability':win,'market_probability':None,'grid':None,'form_score':round(21-f['avg_finish_last_5'],2),'reliability_rate':f['finish_rate_last_10']*100,'constructor_strength':21-f['constructor_avg_finish_last_5'],'factors':factors,'score_breakdown':{'form':21-f['avg_finish_last_5'],'constructor_strength':21-f['constructor_avg_finish_last_5'],'grid':0,'reliability':f['finish_rate_last_10']*100,'points':f['season_points_before_target'],'market':0,'penalty':-f['dnf_rate_last_10']},**MediaService().get(row['driver_id'],row['constructor_ref'])})
        predictions.sort(key=lambda p:(-p['win_probability'],p['driver_id']))
        for i,p in enumerate(predictions,1):p['predicted_position']=i;p['rank']=i
        race=frame['race'];replay=parse_time(race['start_at'] or race['date'])<utcnow()
        response={**news_meta,'race_id':race_id,'race_name':race['race_name'],'season_year':race['season_year'],'round':race['round'],'predictions':predictions,'mode':frame['mode'],'feature_cutoff':frame['feature_cutoff'],
            'training_cutoff':metadata.get('training_cutoff'),'model_version':metadata['model_version'],'model_type':'calibrated_logistic' if model else 'heuristic_baseline','fallback_reason':metadata.get('reason'),
            'historical_replay':replay,'roster_source':frame['roster_source'],'market_factor_used':False,'probability_unit':'fraction','confidence':{'favourite_probability':predictions[0]['win_probability'] if predictions else 0,'label':'uncertainty remains; no certainty claim'},
            'scenario':scenario,'scenario_method':'Feature intervention plus assumed grid odds multiplier exp(0.08*(midfield-grid)) and regulation uncertainty mixing; not a causal estimate' if scenario else None,'limitations':['Practice and actual starting-grid features unavailable','Explanation factors are observations, not causal effects or SHAP']}
        if persist:
            from services.history_service import HistoryService
            response['prediction_run_id']=HistoryService().record('scenario' if scenario else 'race',race_id,predictions,{k:v for k,v in response.items() if k!='predictions'})
        return response
    def latest_forecast(self,race_id):
        from models.weekend import WeekendState
        from database.db import SessionLocal
        with SessionLocal() as s:state=s.get(WeekendState,race_id)
        if state and state.forecasts and state.forecasts.get('race'):return copy.deepcopy(state.forecasts['race'])
        return self.predict_race(race_id,persist=False)
    def predict_race_summary(self,race_id,limit=5,mode='PRE_WEEKEND'):
        response=self.predict_race(race_id,mode);response['total_drivers']=len(response['predictions']);response['predictions']=response['predictions'][:limit];return response
    def predict_race_with_market(self,race_id,odds_data,mode='PRE_WEEKEND',captured_at=None):
        from services.odds.odds_service import OddsService
        from services.history_service import HistoryService
        captured_at=captured_at or iso(utcnow())
        response=self.predict_race(race_id,mode,persist=False)
        response=OddsService().adjust(response,odds_data,captured_at)
        response['prediction_run_id']=HistoryService().record('race_market',race_id,response['predictions'],{k:v for k,v in response.items() if k!='predictions'})
        return response
    def predict_champion(self,season=None):
        return self.championship(season)['drivers']
    def championship(self,season=None,persist=True,simulations=None,seed=None):
        from services.championship_service import ChampionshipSimulationService
        result=ChampionshipSimulationService().simulate(season,simulations,seed)
        if persist:
            from services.history_service import HistoryService
            result['prediction_run_id']=HistoryService().record('champion',None,result['drivers'],{k:v for k,v in result.items() if k!='drivers'})
        return result
    def explain_model(self):
        return {'model_type':'temporal_classification_with_calibration','description':'Pre-race history → logistic classifiers → sigmoid calibration on a later season → race normalization. Historical tests are walk-forward. Championship probabilities come from Monte Carlo, not lifetime points. An explicit heuristic fallback is used when no eligible model is available.','probability_unit':'fraction','explanation_type':'observed factors, not SHAP','market':'Optional timestamped odds; absent odds leave model probabilities unchanged.'}
