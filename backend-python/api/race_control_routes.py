from flask import Blueprint,jsonify,request
from services.race_control_service import RaceControlService
race_control_bp=Blueprint('race_control',__name__)
service=RaceControlService()
@race_control_bp.get('/race-control/<int:race_id>/catalog')
def catalog(race_id):return jsonify(service.catalog(race_id))
@race_control_bp.post('/race-control/<int:race_id>/catalog')
def refresh(race_id):return jsonify(service.catalog(race_id,refresh=True))
@race_control_bp.post('/race-control/<int:race_id>/<int:key>/prepare')
def prepare(race_id,key):return jsonify(service.prepare(race_id,key,(request.get_json(silent=True) or {}).get('mode','REPLAY')))
@race_control_bp.get('/race-control/<int:race_id>/<int:key>/status')
def status(race_id,key):return jsonify(service.status(race_id,key,request.args.get('mode','REPLAY')))
@race_control_bp.get('/race-control/<int:race_id>/<int:key>/frame')
def frame(race_id,key):return jsonify(service.frame(race_id,key,request.args.get('at'),request.args.get('driver',type=int),request.args.get('mode','REPLAY'),request.args.get('window',30,type=int)))
