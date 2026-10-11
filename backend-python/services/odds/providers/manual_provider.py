from services.odds.base import OddsProvider
class ManualOddsProvider(OddsProvider):
    name='manual'
    def __init__(self,rows):self.rows=rows
    def fetch_race_odds(self,race):return self.rows
