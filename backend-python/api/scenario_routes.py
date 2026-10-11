from flask import Blueprint, jsonify, request
from services.scenario_service import ScenarioService

scenario_bp = Blueprint("scenarios", __name__)
service = ScenarioService()


@scenario_bp.route("/scenarios", methods=["GET"])
def list_scenarios():
    return jsonify(service.list_scenarios())


@scenario_bp.route("/scenarios", methods=["POST"])
def create_scenario():
    payload = request.get_json() or {}
    return jsonify(service.create_scenario(payload))


@scenario_bp.route("/scenarios/<scenario_id>", methods=["DELETE"])
def delete_scenario(scenario_id):
    service.delete_scenario(scenario_id)
    return jsonify({"message": "deleted", "id": scenario_id})


@scenario_bp.route("/scenarios/<scenario_id>/run", methods=["POST"])
def run_scenario(scenario_id):
    return jsonify(service.run_scenario(scenario_id))
