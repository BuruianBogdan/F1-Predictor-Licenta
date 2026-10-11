from ml.feature_engineering import FeatureEngineeringService
class OddsProviderService:
    def demo_odds(self,race_id):
        # Equal, obviously synthetic odds, never inferred from actual outcomes.
        rows=FeatureEngineeringService().build(race_id)['rows']
        return [{'driver_id':r['driver_id'],'odds':float(len(rows)),'provider':'demo_synthetic'} for r in rows]
