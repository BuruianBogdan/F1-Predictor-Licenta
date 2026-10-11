import pytest
from services.odds.normalization import normalize
from services.prediction_service import PredictionService

def test_margin_removed_and_multiple_books_aggregated():
    rows=[{'driver_id':1,'odds':2},{'driver_id':2,'odds':3}]
    result=normalize(rows);assert sum(result.values())==pytest.approx(1);assert result[1]==pytest.approx(.6)
    assert sum(normalize(rows+[{'driver_id':1,'odds':2.2,'provider':'b'},{'driver_id':2,'odds':2.8,'provider':'b'}]).values())==pytest.approx(1)

@pytest.mark.parametrize('odds',[1,0,-1,float('nan'),float('inf'),None,'bad'])
def test_invalid_odds_rejected(odds):
    with pytest.raises(ValueError):normalize([{'driver_id':1,'odds':odds}])

def test_duplicate_or_unknown_driver_rejected():
    with pytest.raises(ValueError):normalize([{'driver_id':1,'odds':2}]*2)
    with pytest.raises(ValueError):normalize([{'driver_id':1,'odds':2}],{2})

def test_missing_odds_preserve_distribution_and_partial_book_retains_mass(race_field):
    service=PredictionService();rid=race_field['target']
    base=service.predict_race(rid,persist=False)
    absent=service.predict_race_with_market(rid,[])
    assert [p['win_probability'] for p in base['predictions']]==[p['final_probability'] for p in absent['predictions']]
    combined=service.predict_race_with_market(rid,[{'driver_id':1,'odds':5},{'driver_id':2,'odds':2}],captured_at='2025-04-01T12:00:00Z')
    assert sum(p['final_probability'] for p in combined['predictions'])==pytest.approx(1)
    original={p['driver_id']:p['win_probability'] for p in base['predictions']}
    for p in combined['predictions']:
        if p['driver_id'] not in (1,2):assert p['final_probability']==pytest.approx(original[p['driver_id']])
    with pytest.raises(ValueError,match='after'):service.predict_race_with_market(rid,[{'driver_id':1,'odds':2}])

def test_row_timestamp_cannot_hide_behind_earlier_batch_date(race_field):
    service=PredictionService()
    with pytest.raises(ValueError,match='after'):
        service.predict_race_with_market(race_field['target'],[{'driver_id':1,'odds':3,'captured_at':'2025-05-01T00:00:00Z'}],captured_at='2025-04-01T00:00:00Z')

def test_valid_individual_timestamps_are_preserved(race_field):
    from database.db import SessionLocal
    from models.analytics import OddsSnapshot
    result=PredictionService().predict_race_with_market(race_field['target'],[
        {'driver_id':1,'odds':3,'captured_at':'2025-04-01T12:00:00Z'},
        {'driver_id':2,'odds':4,'captured_at':'2025-04-02T12:00:00Z'}])
    with SessionLocal() as s:
        snapshot=s.get(OddsSnapshot,result['odds_snapshot_id'])
        assert snapshot.captured_at.startswith('2025-04-02')
        assert snapshot.data[0]['captured_at'].startswith('2025-04-01')
