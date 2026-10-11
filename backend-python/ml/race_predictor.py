"""Legacy entry point delegates to the cutoff-safe pipeline."""
class RacePredictor:
    def predict(self,race_id,regulation_factor=1.0):
        from services.prediction_service import PredictionService
        return PredictionService().predict_race(race_id)
