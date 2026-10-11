"""Manual refresh remains independent of removed data-platform modules."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import json
import pytest
from services import session_refresh_service as module
from services.session_refresh_service import SessionRefreshService
from services.job_service import JobService

NOW=datetime.now(timezone.utc)

def setup(monkeypatch, missing=(1,2), source_error=None):
    race={'race_id':9,'race_name':'Test GP','start_at':(NOW+timedelta(days=1)).isoformat(),'date':(NOW+timedelta(days=1)).date().isoformat(),'season_year':NOW.year}
    monkeypatch.setattr(module.SeasonContext,'get',lambda _: {'next_race':race})
    sessions=[]
    for key,code,name,state,offset in [(1,'FP1','Practice 1','REPLAY',-8),(2,'SQ','Sprint Qualifying','REPLAY',-6),(3,'Q','Qualifying','LIVE_WINDOW',-.2),(4,'R','Race','UPCOMING',24)]:
        sessions.append({'session_key':key,'code':code,'session_name':name,'state':state,'date_start':(NOW+timedelta(hours=offset)).isoformat(),'date_end':(NOW+timedelta(hours=offset+1)).isoformat(),'archive_at':(NOW+timedelta(hours=offset+1.5)).isoformat()})
    calls=[];cached={key:True for key in [1,2] if key not in missing};downloads=[]
    def catalog(rid,refresh=False):calls.append((rid,refresh));return {'sessions':sessions,'error':source_error,'race':race,'as_of':NOW.isoformat()}
    def prepare(rid,key,mode):downloads.append((rid,key,mode));cached[key]=True;return {'status':'SUCCESS'}
    service=SimpleNamespace(catalog=catalog,load=lambda key:cached.get(key),covered=bool,jobs={},prepare=prepare)
    checks=[];weekend=SimpleNamespace(refresh=lambda rid,**kwargs:checks.append((rid,kwargs)))
    return SessionRefreshService(service=service,weekend=weekend),calls,downloads,checks

def test_manual_refresh_forces_catalog_and_downloads_every_public_session(monkeypatch):
    worker,calls,downloads,checks=setup(monkeypatch);progress=[]
    result=worker.tick(force=True,progress=progress.append)
    assert calls==[(9,True)] and downloads==[(9,2,'REPLAY'),(9,1,'REPLAY')] and checks==[(9,{'force':True})]
    assert result['status']=='SUCCESS' and len(result['sessions'])==4
    assert all(row['downloaded'] for row in result['sessions'][:2])
    assert result['sessions'][2]['status']=='LIVE_WINDOW' and result['sessions'][2]['replay_url'] is None
    assert all(row['viewer_url'].startswith('/race-control/') for row in result['sessions'])
    assert [p['phase'] for p in progress]==['CATALOG','RESULTS','COMPLETE']

def test_source_refusal_keeps_existing_replays_and_reports_partial(monkeypatch):
    worker,_,downloads,_=setup(monkeypatch,missing=(),source_error='Source access refused')
    result=worker.tick(force=True)
    assert result['status']=='PARTIAL' and result['warnings']==['Source access refused']
    assert len(result['sessions'])==4 and result['sessions'][0]['downloaded'] and downloads==[]

def test_checks_share_one_acquisition_lock(monkeypatch):
    worker,_,downloads,_=setup(monkeypatch);worker.work_lock.acquire()
    try:assert worker.tick()=={'status':'BUSY'} and downloads==[]
    finally:worker.work_lock.release()

def test_repeated_button_clicks_return_the_same_running_job(monkeypatch):
    worker=SessionRefreshService();calls=[];monkeypatch.setattr(JobService,'jobs',{})
    def submit(label,operation):
        calls.append(label);JobService.jobs['one']={'id':'one','status':'QUEUED'};return JobService.jobs['one']
    monkeypatch.setattr(JobService,'submit',submit)
    assert worker.refresh()['id']=='one' and worker.refresh()['id']=='one' and len(calls)==1

@pytest.mark.parametrize('wrong_date',[False,True])
def test_persistent_catalog_restores_only_matching_verified_meetings(tmp_path,wrong_date):
    race={'race_id':9,'date':'2026-10-11','season_year':2026}
    row={'session_name':'Race','date_start':'2026-10-11T12:00:00+00:00','meeting_key':1296}
    (tmp_path/'session-catalog-9.json').write_text(json.dumps({'race_id':9,'date':'2026-09-01' if wrong_date else race['date'],'season_year':2026,'rows':[row]}))
    stored={};service=SimpleNamespace(cache_dir=tmp_path,catalogs=stored,race_info=lambda _: (race,None),catalog=lambda *a,**k:{'sessions':[], 'error':'source offline'})
    SessionRefreshService(service=service).catalog(9,True)
    assert bool(stored)==(not wrong_date)

def test_no_published_sessions_does_not_report_success(monkeypatch):
    worker,_,downloads,_=setup(monkeypatch)
    worker.service.catalog=lambda *a,**k:{'sessions':[], 'error':None}
    assert worker.tick(force=True)['status']=='PARTIAL' and downloads==[]

def test_just_started_gp_is_selected_before_the_next_weekend(monkeypatch):
    worker,_,_,_=setup(monkeypatch,missing=())
    current={'race_id':9,'race_name':'Current GP','start_at':(NOW-timedelta(hours=1)).isoformat()}
    monkeypatch.setattr(module.SeasonContext,'get',lambda _: {'next_race':{'race_id':10,'start_at':(NOW+timedelta(days=14)).isoformat()},'awaiting_results':[current]})
    seen=[];worker.service.catalog=lambda rid,**k:seen.append(rid) or {'sessions':[], 'error':None}
    worker.tick(force=True);assert seen==[9]
