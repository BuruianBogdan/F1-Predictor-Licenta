from flask import Blueprint,jsonify,request,abort
from database.db import SessionLocal,engine
from sqlalchemy import text
from models.analytics import DataSyncRun,PredictionRun
from services.season_service import SeasonContext,utcnow,iso
from services.data_sync_service import F1DataSyncService
from services.data_quality_service import DataQualityService
from services.insight_service import InsightService
from services.prediction_service import PredictionService
from services.odds.odds_service import OddsService
from services.llm_service import LLMExplanationService
from services.job_service import JobService
from ml.training import metrics,train
from ml.race_model import load_for_cutoff
from config import USE_SELENIUM_ODDS,LLM_ENABLED

intelligence_bp=Blueprint('intelligence',__name__)

@intelligence_bp.get('/health')
def health():
    with engine.connect() as c:c.execute(text('SELECT 1'))
    context=SeasonContext().get();model,_=load_for_cutoff(iso(utcnow()))
    return jsonify(status='ok',database='ok',model='loaded' if model else 'heuristic_fallback',season=context['active_season'],last_data_sync=context['last_sync_at'],odds='enabled' if USE_SELENIUM_ODDS else 'disabled',llm='enabled' if LLM_ENABLED else 'disabled')

@intelligence_bp.get('/season/context')
def season_context():return jsonify(SeasonContext().get())

@intelligence_bp.post('/data/sync/current')
def sync_current():
    if request.args.get('background')=='true':return jsonify(JobService.submit('Sync current season',F1DataSyncService().sync_current_season)),202
    return jsonify(F1DataSyncService().sync_current_season())

@intelligence_bp.post('/data/sync/season/<int:year>')
def sync_season(year):return jsonify(F1DataSyncService().sync_season(year))

@intelligence_bp.post('/data/sync/history')
def sync_history():
    data=request.get_json() or {};start=int(data.get('start_year',2014));end=int(data.get('end_year',utcnow().year))
    if not 1950<=start<=end<=utcnow().year:raise ValueError('Invalid history range')
    from services.import_service import ImportService
    return jsonify(JobService.submit(f'Sync {start}–{end}',lambda:ImportService().import_historical_data(start,end))),202

@intelligence_bp.get('/data/jobs/<job_id>')
def job(job_id):
    if job_id not in JobService.jobs:abort(404,description='Job not found; local jobs do not survive server restart')
    return jsonify(JobService.jobs[job_id])

@intelligence_bp.get('/data/sync/status')
def sync_status():
    with SessionLocal() as s:runs=s.query(DataSyncRun).order_by(DataSyncRun.id.desc()).limit(20).all()
    return jsonify(runs=[{'id':r.id,'season':r.season,'status':r.status,'started_at':r.started_at,'completed_at':r.completed_at,'summary':r.summary} for r in runs],context=SeasonContext().get())

@intelligence_bp.get('/data/quality')
def quality():return jsonify(DataQualityService().report())

@intelligence_bp.get('/races/<int:race_id>/detail')
def race_detail(race_id):return jsonify(InsightService().race_detail(race_id))

@intelligence_bp.get('/drivers/<int:driver_id>/detail')
def driver_detail(driver_id):return jsonify(InsightService().driver_detail(driver_id))

@intelligence_bp.get('/model/metrics')
def model_metrics():return jsonify(metrics(request.args.get('mode','PRE_WEEKEND').upper()))

@intelligence_bp.post('/model/retrain')
def retrain():
    data=request.get_json() or {};mode=data.get('mode','PRE_WEEKEND').upper()
    if mode not in ('PRE_WEEKEND','POST_QUALIFYING'):raise ValueError('Unsupported training mode')
    through=int(data.get('through_season',utcnow().year-1))
    return jsonify(JobService.submit('Train model with temporal validation',lambda:train(through,mode))),202

@intelligence_bp.get('/predict/championship')
def championship():return jsonify(PredictionService().championship(request.args.get('season',type=int),simulations=request.args.get('simulations',type=int),seed=request.args.get('seed',type=int)))

@intelligence_bp.get('/odds/status')
def odds_status():return jsonify(OddsService().status())

@intelligence_bp.get('/odds/<int:race_id>')
def odds(race_id):return jsonify(OddsService().get(race_id))

@intelligence_bp.post('/odds/refresh/<int:race_id>')
def refresh_odds(race_id):return jsonify(OddsService().refresh(race_id))

@intelligence_bp.post('/explanations/prediction/<run_id>')
def prediction_explanation(run_id):
    with SessionLocal() as s:run=s.get(PredictionRun,run_id)
    if not run:abort(404,description='Prediction run not found')
    return jsonify(LLMExplanationService().explain({'predictions':run.predictions,'metadata':run.meta},language=request.args.get('lang','en')))

@intelligence_bp.post('/explanations/race/<int:race_id>')
def recap(race_id):return jsonify(LLMExplanationService().explain(InsightService().race_detail(race_id),'recap',request.args.get('lang','en')))
