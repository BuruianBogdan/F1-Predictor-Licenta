from flask import Blueprint,jsonify,request
from services.weekend_service import WeekendService
from services.live_prediction_service import LivePredictionService
from services.job_service import JobService
weekend_bp=Blueprint('weekend',__name__)
@weekend_bp.get('/weekend/<int:race_id>')
def status(race_id):return jsonify(WeekendService().status(race_id))
@weekend_bp.post('/weekend/<int:race_id>/refresh')
def refresh(race_id):
    if not WeekendService().status(race_id)['refresh_allowed']:raise ValueError('Weekend refresh is only available before the Grand Prix starts')
    return jsonify(JobService.submit('Update weekend and recalculate Grand Prix, sprint and championship',lambda:WeekendService().refresh(race_id))),202
@weekend_bp.get('/predict/live/<int:race_id>')
def predict_live(race_id):return jsonify(LivePredictionService().predict(race_id,request.args.get('target','RACE'),persist=False))
@weekend_bp.get('/predict/sprint/<int:race_id>')
def predict_sprint(race_id):return jsonify(LivePredictionService().predict(race_id,'SPRINT',pre_weekend=request.args.get('mode','LIVE').upper()=='PRE_WEEKEND'))
