from flask import Blueprint, jsonify, request
from services.standings_service import StandingsService

standings_bp = Blueprint("standings", __name__)

service = StandingsService()


@standings_bp.route("/standings/drivers", methods=["GET"])
def get_driver_standings():
    standings = service.get_driver_standings(request.args.get("season", type=int))
    return jsonify(standings)


@standings_bp.route("/standings/constructors", methods=["GET"])
def get_constructor_standings():
    standings = service.get_constructor_standings(request.args.get("season", type=int))
    return jsonify(standings)