import pytest
from services.prediction_service import PredictionService

def test_hypothetical_grid_changes_probability_without_changing_facts(race_field):
    service=PredictionService();rid=race_field['target']
    before=service.predict_race(rid,persist=False)
    pole=service.predict_race(rid,persist=False,scenario={'driver_id':8,'grid_position':1})
    back=service.predict_race(rid,persist=False,scenario={'driver_id':8,'grid_position':12})
    probability=lambda result:next(p['win_probability'] for p in result['predictions'] if p['driver_id']==8)
    assert probability(pole)>probability(back)
    assert service.predict_race(rid,persist=False)['predictions']==before['predictions']
    assert sum(p['win_probability'] for p in pole['predictions'])==pytest.approx(1)

def test_wet_scenario_explicitly_reduces_certainty(race_field):
    service=PredictionService();rid=race_field['target']
    dry=service.predict_race(rid,persist=False,scenario={'wet_race':False})
    wet=service.predict_race(rid,persist=False,scenario={'wet_race':True})
    assert wet['predictions'][0]['win_probability']<dry['predictions'][0]['win_probability']
