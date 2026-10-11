from flask import Blueprint, jsonify, request
from services.prediction_service import PredictionService

prediction_bp = Blueprint("prediction", __name__)

service = PredictionService()

@prediction_bp.get('/predict/availability')
def prediction_availability():
    return jsonify(service.available_modes(request.args.get('season',type=int)))


@prediction_bp.route("/predict/champion", methods=["GET"])
def predict_champion():
    return jsonify(service.predict_champion(request.args.get("season", type=int)))


@prediction_bp.route("/predict/race/<int:race_id>", methods=["GET"])
def predict_race(race_id):
    return jsonify(service.predict_race(race_id, request.args.get("mode", "PRE_WEEKEND")))


@prediction_bp.route("/predict/race/<int:race_id>/summary", methods=["GET"])
def predict_race_summary(race_id):
    limit = request.args.get("limit", 5, type=int)
    limit = max(1, min(limit, 20))
    return jsonify(service.predict_race_summary(race_id, limit=limit, mode=request.args.get("mode", "PRE_WEEKEND")))


@prediction_bp.route("/predict/race/<int:race_id>/market", methods=["POST"])
def predict_race_with_market(race_id):
    data = request.get_json() or {}
    odds = data.get("odds", [])
    return jsonify(service.predict_race_with_market(race_id, odds, data.get("mode", "PRE_WEEKEND"), data.get("captured_at")))


@prediction_bp.route("/predict/explain", methods=["GET"])
def explain_model():
    return jsonify(service.explain_model())
