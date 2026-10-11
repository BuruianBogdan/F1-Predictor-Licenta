from flask import Blueprint, Response
from services.export_service import ExportService

export_bp = Blueprint("export", __name__)
service = ExportService()


def _csv(content, filename):
    return Response(
        content,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@export_bp.route("/export/champion.csv", methods=["GET"])
def export_champion():
    return _csv(service.champion_csv(), "champion.csv")


@export_bp.route("/export/race/<int:race_id>.csv", methods=["GET"])
def export_race(race_id):
    return _csv(service.race_csv(race_id), f"race_{race_id}.csv")


@export_bp.route("/export/report.txt", methods=["GET"])
def export_report():
    return Response(
        service.full_report_text(),
        mimetype="text/plain",
        headers={"Content-Disposition": 'attachment; filename="report.txt"'},
    )

@export_bp.get('/export/history.csv')
def export_history():return _csv(service.history_csv(),'prediction-history.csv')

@export_bp.get('/export/metrics.csv')
def export_metrics():return _csv(service.metrics_csv(),'model-metrics.csv')
