from database.db import SessionLocal
from models.race_result import RaceResult
from ml.feature_engineering import FeatureEngineeringService
from services.prediction_service import PredictionService

def test_target_and_future_outcomes_cannot_change_pre_weekend_features(race_field):
    target=race_field['target']
    before=FeatureEngineeringService().build(target)['rows']
    probabilities=PredictionService().predict_race(target,persist=False)['predictions']
    with SessionLocal.begin() as s:
        for r in s.query(RaceResult).filter(RaceResult.race_id.in_([target,race_field['future']])).all():
            r.position=13-r.position;r.points=999;r.status='Engine';r.grid=1;r.fastest_lap='0:01.000';r.laps=999
    after=FeatureEngineeringService().build(target)['rows']
    assert before==after
    assert probabilities==PredictionService().predict_race(target,persist=False)['predictions']

def test_chronology_uses_dates_not_database_ids(race_field):
    frame=FeatureEngineeringService().build(race_field['target'])
    assert all(r['features']['races_started_before_target']==2 for r in frame['rows'])
    assert all(r['features']['qualifying_known']==0 and r['features']['grid_known']==0 for r in frame['rows'])

def test_dataset_target_is_label_only(race_field):
    from ml.feature_engineering import FEATURES
    assert not {'position','points','status','winner','podium','race_id','driver_id'}&set(FEATURES)
    data=FeatureEngineeringService().dataset()
    assert not data.empty
    assert (data.feature_cutoff.str[:10]<data.date).all()
