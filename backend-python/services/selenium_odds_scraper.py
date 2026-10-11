from config import USE_SELENIUM_ODDS
from services.odds.odds_service import OddsService

def is_enabled():return USE_SELENIUM_ODDS
def fetch_odds(race_id):
    if not is_enabled():return []
    data=OddsService().refresh(race_id)
    return [r for s in data.get('snapshots',[]) for r in s['odds'] if not s['stale']]
