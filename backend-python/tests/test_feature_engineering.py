import pytest
from datetime import datetime,timezone
from ml.feature_engineering import FeatureEngineeringService,is_finished
from services.prediction_service import PredictionService

def test_qualifying_available_only_in_correct_mode(race_field):
    service=FeatureEngineeringService()
    assert all(r['features']['qualifying_known']==1 for r in service.build(race_field['target'],'POST_QUALIFYING')['rows'])
    with pytest.raises(ValueError,match='not available'):
        service.build(race_field['target'],'POST_QUALIFYING',datetime(2025,3,2,tzinfo=timezone.utc))

def test_all_lapped_finishes_are_classified():
    assert is_finished('+2 Laps') and is_finished('+1 Lap') and is_finished('Finished')
    assert not is_finished('Engine')

def test_probabilities_are_coherent(race_field):
    response=PredictionService().predict_race(race_field['target'])
    assert response['historical_replay'] is True
    assert sum(p['win_probability'] for p in response['predictions'])==pytest.approx(1)
    for p in response['predictions']:assert 0<=p['win_probability']<=p['podium_probability']<=p['points_probability']<=1
    assert response['prediction_run_id']
