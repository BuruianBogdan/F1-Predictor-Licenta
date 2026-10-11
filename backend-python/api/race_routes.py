from flask import Blueprint, request, jsonify
from services.race_service import RaceService

race_bp = Blueprint("race", __name__)

service = RaceService()


@race_bp.route("/races", methods=["GET"])
def get_races():
    races = service.get_races()
    return jsonify(races)


@race_bp.route("/races/<int:race_id>", methods=["GET"])
def get_race(race_id):
    race = service.get_race(race_id)
    if race:
        return jsonify(race)
    return jsonify({"message": "Race not found"}), 404


@race_bp.route("/races", methods=["POST"])
def create_race():
    data = request.get_json()
    race = service.create_race(data)
    return jsonify(race), 201


@race_bp.route("/races/<int:race_id>", methods=["PUT"])
def update_race(race_id):
    data = request.get_json()
    updated_race = service.update_race(race_id, data)

    if updated_race:
        return jsonify(updated_race)

    return jsonify({"message": "Race not found"}), 404


@race_bp.route("/races/<int:race_id>", methods=["DELETE"])
def delete_race(race_id):
    service.remove_race(race_id)
    return jsonify({"message": "Race deleted successfully"})