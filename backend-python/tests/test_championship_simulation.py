from datetime import date,timedelta
import pytest
from database.db import SessionLocal
from models.race import Race
from services.championship_service import ChampionshipSimulationService
from services.season_service import utcnow

def test_simulation_reproducible_valid_and_never_loses_current_points(race_field):
    with SessionLocal.begin() as s:
        future=utcnow().date()+timedelta(days=10)
        s.add(Race(race_id=999,season_year=2025,round=6,circuit_id=1,race_name='Future fixture',date=future,start_at=f'{future}T14:00:00Z',is_completed=0,results_verified=0,race_status='SCHEDULED'))
    service=ChampionshipSimulationService()
    a=service.simulate(2025,300,42);b=service.simulate(2025,300,42)
    assert a['drivers']==b['drivers']
    assert sum(p['championship_probability'] for p in a['drivers'])==pytest.approx(1)
    assert a['remaining_races']==1
    assert all(p['expected_final_points']>=p['current_points'] for p in a['drivers'])

def test_completed_championship_resolves_countback(race_field):
    response=ChampionshipSimulationService().simulate(2025,100,1)
    assert response['remaining_races']==0
    assert response['drivers'][0]['driver_id']==1
    assert response['drivers'][0]['championship_probability']==1

def test_grand_prix_news_penalty_does_not_reduce_sprint_points(race_field,monkeypatch):
    import numpy as np
    from services.prediction_service import PredictionService
    import services.championship_service as module
    with SessionLocal.begin() as s:
        future=utcnow().date()+timedelta(days=10)
        s.add(Race(race_id=999,season_year=2025,round=6,circuit_id=1,race_name='Sprint weekend',date=future,start_at=f'{future}T14:00:00Z',sprint_at=f'{future-timedelta(days=1)}T14:00:00Z',is_completed=0,results_verified=0,race_status='SCHEDULED'))
    # Isolate points awarded by the sprint, using common random draws and a fixed roster.
    monkeypatch.setattr(module,'POINTS',np.zeros(10))
    predictions=[{'driver_id':d,'win_probability':1/12,'base_model_probability':1/12,'reliability_rate':99} for d in range(1,13)]
    monkeypatch.setattr(PredictionService,'predict_race',lambda *a,**kw:{'predictions':predictions,'news_factor_used':True})
    service=ChampionshipSimulationService();baseline=service.simulate(2025,300,42)
    predictions[0]['win_probability']=.001
    for p in predictions[1:]:p['win_probability']=.999/11
    adjusted=service.simulate(2025,300,42)
    totals=lambda result:{p['driver_id']:p['expected_final_points'] for p in result['drivers']}
    assert totals(baseline)==totals(adjusted)
