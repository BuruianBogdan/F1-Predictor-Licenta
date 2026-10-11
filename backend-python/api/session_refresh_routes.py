from flask import Blueprint, jsonify, request
from services.session_refresh_service import SessionRefreshService

session_refresh_bp = Blueprint('session_refresh', __name__)
service = SessionRefreshService()

@session_refresh_bp.get('/race-control/sessions/refresh')
def status():
    return jsonify(service.status())

@session_refresh_bp.post('/race-control/sessions/refresh')
def refresh():
    body = request.get_json(silent=True) or {}
    return jsonify(service.refresh(body.get('race_id'))), 202
