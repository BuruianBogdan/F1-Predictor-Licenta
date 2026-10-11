from flask import Blueprint, jsonify, request
from services.regulation_service import RegulationService

regulation_bp = Blueprint("regulations", __name__)
service = RegulationService()


@regulation_bp.route("/regulations", methods=["GET"])
def get_regulations():
    return jsonify(service.get())


@regulation_bp.route("/regulations", methods=["POST"])
def save_regulations():
    payload = request.get_json() or {}
    return jsonify(service.save(payload))


@regulation_bp.route("/regulations/reset", methods=["POST"])
def reset_regulations():
    return jsonify(service.reset())
