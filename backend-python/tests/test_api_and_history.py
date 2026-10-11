import pytest
from app import app
from database.db import SessionLocal
from models.analytics import PredictionRun
from services.prediction_service import PredictionService
from services.history_service import HistoryService

@pytest.mark.parametrize('entity,payload,change',[
 ('drivers',{'driver_ref':'new','forename':'New','surname':'Pilot','number':99,'code':'NEW','nationality':'Test','dob':'2000-01-01'},{'surname':'Changed'}),
 ('constructors',{'constructor_ref':'new','name':'New Team','nationality':'Test'},{'name':'Changed'}),
 ('circuits',{'circuit_ref':'new','name':'New Circuit','location':'Local','country':'Test','lat':1,'lng':2},{'name':'Changed'}),
 ('races',{'season_year':2025,'round':99,'circuit_id':1,'race_name':'New Race','date':'2025-12-01'},{'race_name':'Changed'}),
])
def test_original_crud_contracts(race_field,entity,payload,change):
    client=app.test_client();created=client.post('/'+entity,json=payload);assert created.status_code in (200,201)
    singular={'drivers':'driver','constructors':'constructor','circuits':'circuit','races':'race'}[entity];id=created.json[singular+'_id']
    assert client.get(f'/{entity}/{id}').status_code==200
    updated=client.put(f'/{entity}/{id}',json=change);assert updated.status_code==200
    for k,v in change.items():assert updated.json[k]==v
    assert client.delete(f'/{entity}/{id}').status_code==200
    missing=client.get(f'/{entity}/{id}')
    assert missing.status_code==404
    assert missing.json['error']['code']=='NOT_FOUND'

def test_result_crud_and_link_protection(race_field):
    client=app.test_client()
    driver=client.post('/drivers',json={'driver_ref':'extra','forename':'Extra','surname':'Pilot'}).json
    result=client.post('/results',json={'race_id':race_field['target'],'driver_id':driver['driver_id'],'constructor_id':1,'position':13,'grid':13,'points':0,'status':'Finished'})
    assert result.status_code==201
    rid=result.json['result_id'];assert client.put(f'/results/{rid}',json={'status':'Engine'}).json['status']=='Engine'
    assert client.delete('/drivers/'+str(driver['driver_id'])).status_code==409
    assert client.delete(f'/results/{rid}').status_code==200
    assert client.delete('/drivers/'+str(driver['driver_id'])).status_code==200

def test_replays_cannot_be_claimed_as_prospective_accuracy(race_field):
    result=PredictionService().predict_race(race_field['target']);HistoryService().evaluate_all()
    with SessionLocal() as s:
        run=s.get(PredictionRun,result['prediction_run_id']);assert run.replay;assert run.accuracy['prospective'] is False

def test_dashboard_get_does_not_create_prediction_runs(race_field):
    client=app.test_client();before=None
    with SessionLocal() as s:before=s.query(PredictionRun).count()
    assert client.get('/dashboard/overview').status_code==200
    with SessionLocal() as s:assert s.query(PredictionRun).count()==before

def test_consistent_error_and_health():
    client=app.test_client();assert client.get('/health').status_code==200
    response=client.get('/missing-route');assert response.status_code==404;assert response.json['error']['code']=='NOT_FOUND'
    assert client.post('/data/sync/current',environ_base={'REMOTE_ADDR':'10.1.2.3'}).status_code==403

def test_qualifying_availability_matches_cutoff_and_returns_actionable_error(race_field):
    from models.analytics import QualifyingResult
    from datetime import timedelta
    from services.season_service import utcnow,iso
    client=app.test_client();rid=race_field['target']
    assert client.get('/predict/availability?season=2025').json[str(rid)]['post_qualifying_available'] is True
    with SessionLocal.begin() as s:
        for row in s.query(QualifyingResult).filter_by(race_id=rid):row.available_at=iso(utcnow()+timedelta(days=1))
    assert client.get('/predict/availability?season=2025').json[str(rid)]['post_qualifying_available'] is False
    for response in [client.get(f'/predict/race/{rid}?mode=POST_QUALIFYING'),client.post(f'/predict/race/{rid}/market',json={'mode':'POST_QUALIFYING','odds':[]})]:
        assert response.status_code==400
        assert response.json['error']['code']=='QUALIFYING_UNAVAILABLE'
    assert client.get(f'/predict/race/{rid}?mode=PRE_WEEKEND').status_code==200
