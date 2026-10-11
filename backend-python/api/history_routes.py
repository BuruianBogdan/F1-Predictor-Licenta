from flask import Blueprint, jsonify
from services.history_service import HistoryService

history_bp = Blueprint("history", __name__)
service = HistoryService()


@history_bp.route("/prediction-history", methods=["GET"])
def list_history():
    return jsonify(service.list_history())


@history_bp.route("/prediction-history/evaluate", methods=["POST"])
def evaluate():
    return jsonify(service.evaluate_all())
