import copy
from datetime import timedelta
import pytest
from sqlalchemy import func
from database.db import SessionLocal
from models.race import Race
from models.race_result import RaceResult
from services.data_sync_service import F1DataSyncService
from services.season_service import SeasonContext,utcnow
from data_sources.jolpica_provider import JolpicaProvider
from data_sources.base_provider import ProviderError

class FixtureProvider:
    name='jolpica'
    def __init__(self):
        self.year=utcnow().year;past=str(utcnow().date()-timedelta(days=10));future=str(utcnow().date()+timedelta(days=10))
        circuit={'circuitId':'test','circuitName':'Fixture circuit','Location':{'locality':'Local','country':'Test','lat':'1','long':'2'}}
        self.schedule=[{'season':str(self.year),'round':str(i),'raceName':f'Race {i}','Circuit':circuit,'date':day,'time':'12:00:00Z'} for i,day in [(1,past),(2,future)]]
        self.results=[{**self.schedule[0],'Results':[{'Driver':{'driverId':f'd{d}','givenName':'Pilot','familyName':str(d)},'Constructor':{'constructorId':f't{(d+1)//2}','name':'Team'},'position':str(d),'grid':str(d),'points':str(max(0,26-2*d)),'status':'Finished'} for d in range(1,13)]}]
    def fetch_races(self,year):return copy.deepcopy(self.schedule)
    def fetch_results(self,year):return copy.deepcopy(self.results)
    def fetch_qualifying(self,year):return []
    def fetch_sprints(self,year):return []
    def fetch_standings(self,year,kind):return []

def test_sync_idempotent_corrects_facts_and_keeps_future_scheduled():
    provider=FixtureProvider();service=F1DataSyncService(provider)
    first=service.sync_current_season();second=service.sync_current_season()
    assert first['results_inserted']==12 and second['results_inserted']==0 and second['results_updated']==0
    assert second['entries_inserted']==0 and second['entries_updated']==0
    with SessionLocal() as s:
        assert s.query(Race).count()==2;assert s.query(RaceResult).count()==12
        future=s.query(Race).filter_by(round=2).one();assert future.is_completed==0
    provider.results[0]['Results'][0]['points']='25'
    provider.schedule[1]['date']=str(utcnow().date()+timedelta(days=12))
    fixed=service.sync_current_season();assert fixed['results_updated']==1 and fixed['races_updated']==1
    context=SeasonContext().get();assert context['latest_completed_race']['round']==1;assert context['next_race']['round']==2

def test_failed_sync_rolls_back_facts_but_records_failure():
    provider=FixtureProvider();service=F1DataSyncService(provider);service.sync_current_season()
    provider.schedule[0]['raceName']='Must not be committed';provider.results[0]['Results']=provider.results[0]['Results'][:2]
    with pytest.raises(ProviderError):service.sync_current_season()
    with SessionLocal() as s:assert s.query(Race).filter_by(round=1).one().race_name=='Race 1'

def test_postponed_race_becomes_scheduled_when_calendar_restores_it():
    provider=FixtureProvider();service=F1DataSyncService(provider);service.sync_current_season()
    postponed=provider.schedule.pop()
    service.sync_current_season()
    with SessionLocal() as s:assert s.query(Race).filter_by(round=2).one().race_status=='POSTPONED'
    assert SeasonContext().get()['next_race'] is None
    provider.schedule.append(postponed)
    service.sync_current_season()
    assert SeasonContext().get()['next_race']['round']==2

def test_nested_pagination_merges_races(monkeypatch):
    provider=JolpicaProvider(cache=False);calls=[]
    def get(path,offset):
        calls.append(offset);return {'total':'125','limit':'100','offset':str(offset),'RaceTable':{'Races':[{'season':'2025','round':'1','Results':[{'n':x} for x in range(offset,min(offset+100,125))]}]}}
    monkeypatch.setattr(provider,'_get',get)
    races=provider.fetch_results(2025);assert calls==[0,100];assert len(races)==1;assert len(races[0]['Results'])==125

def test_empty_mid_page_is_failure(monkeypatch):
    provider=JolpicaProvider(cache=False)
    monkeypatch.setattr(provider,'_get',lambda path,offset:{'total':'125','limit':'100','offset':str(offset),'RaceTable':{'Races':[]}})
    with pytest.raises(ProviderError):provider.fetch_results(2025)
