from flask import Blueprint, jsonify, request
from services.odds_provider_service import OddsProviderService
from services.selenium_odds_scraper import fetch_odds, is_enabled

odds_bp = Blueprint("odds", __name__)
provider = OddsProviderService()


@odds_bp.route("/odds/demo/<int:race_id>", methods=["GET"])
def demo_odds(race_id):
    return jsonify({
        "race_id": race_id,
        "odds": provider.demo_odds(race_id),
        "source": "demo",
    })


@odds_bp.route("/odds/live/<int:race_id>", methods=["GET"])
def live_odds(race_id):
    odds = fetch_odds(race_id) if is_enabled() else []
    return jsonify({
        "race_id": race_id,
        "odds": odds,
        "source": "selenium" if is_enabled() else "disabled",
        "enabled": is_enabled(),
    })


@odds_bp.route('/data/refresh-live', methods=['POST'])
def refresh_live():
    from services.data_sync_service import F1DataSyncService
    summary=F1DataSyncService().sync_current_season()
    return jsonify({'message':'Current season synchronized','summary':summary})
