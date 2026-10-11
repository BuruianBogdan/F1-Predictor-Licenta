from flask import Blueprint, jsonify
from services.dashboard_service import DashboardService

dashboard_bp = Blueprint("dashboard", __name__)
service = DashboardService()


@dashboard_bp.route("/dashboard/stats", methods=["GET"])
def stats():
    return jsonify(service.get_stats())


@dashboard_bp.route("/dashboard/overview", methods=["GET"])
def overview():
    return jsonify(service.get_overview())
