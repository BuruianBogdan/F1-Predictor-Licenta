from services.odds.normalization import normalize
class MarketFactorService:
    def build_market_scores(self,odds_data):return normalize(odds_data)
