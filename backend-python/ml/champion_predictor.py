"""Legacy entry point delegates to Monte Carlo simulation."""
class ChampionPredictor:
    def predict(self,regulation_factor=1.0):
        from services.prediction_service import PredictionService
        return PredictionService().predict_champion()
