from flask import Blueprint, request, jsonify
from services.import_service import ImportService

import_bp = Blueprint("import_data", __name__)

service = ImportService()


@import_bp.route("/data/import", methods=["POST"])
def import_data():
    data = request.get_json() or {}

    start_year = data.get("start_year")
    end_year = data.get("end_year")

    if start_year is None or end_year is None:
        return jsonify({"message": "start_year and end_year are required"}), 400

    try:
        start_year = int(start_year)
        end_year = int(end_year)
    except (TypeError, ValueError):
        return jsonify({"message": "start_year and end_year must be integers"}), 400

    if start_year > end_year:
        return jsonify({"message": "start_year must be <= end_year"}), 400

    summary = service.import_historical_data(start_year, end_year)
    return jsonify({"message": "Historical data imported successfully", "summary": summary})
