"""Offline protocol/failure tests. Fixtures are not evidence of public live access."""
import base64
import copy
import json
import time
import zlib
from datetime import datetime,timezone
from pathlib import Path
import pytest
from data_sources.timing_contract import FeedHealth,PatchLedger,TimingSettings,decode_channel,utc_stamp,utc_iso,validate_identity
from data_sources.public_timing_provider import PublicTimingFeed
from services.race_control_checkpoint import TimingCheckpointStore
from services.race_control_service import RaceControlService
from services.race_control_projection_service import RaceControlProjectionService,points_table
from database.db import SessionLocal
from models.analytics import SprintResult


def compressed(value,raw=True):
    compressor=zlib.compressobj(wbits=-15 if raw else 15)
    return base64.b64encode(compressor.compress(json.dumps(value).encode())+compressor.flush()).decode()


@pytest.mark.parametrize('raw',[True,False])
def test_decoder_raw_deflate_and_zlib(raw):
    assert decode_channel(compressed({'Position':[]},raw))=={'Position':[]}


@pytest.mark.parametrize('value',['%%%','',base64.b64encode(b'not zlib').decode(),compressed([])])
def test_decoder_rejects_malformed_channels(value):
    with pytest.raises(ValueError):decode_channel(value)


def test_decoder_rejects_compression_bombs_truncation_and_trailing_streams():
    encoded=compressed({'big':'x'*10000})
    with pytest.raises(ValueError,match='decoded size'):decode_channel(encoded,max_decoded=1000)
    with pytest.raises(ValueError):decode_channel(encoded[:-4])
    with pytest.raises(ValueError):decode_channel(base64.b64encode(base64.b64decode(encoded)+b'extra').decode())


def test_timestamped_sparse_leaf_merge_deduplicates_and_preserves_false_null():
    ledger=PatchLedger(7,max_ids=3)
    first,_,_=ledger.apply('TimingData',{}, {'Lines':{'3':{'InPit':True,'Sectors':[{'Value':'27'},None,{'Value':'25'}]}}},100,101)
    second,changed,_=ledger.apply('TimingData',first,{'Lines':{'3':{'InPit':False,'GapToLeader':None,'Sectors':{'1':{'Value':'39'}}}}},102,103)
    assert changed and second['Lines']['3']['InPit'] is False and second['Lines']['3']['GapToLeader'] is None
    old,_,_=ledger.apply('TimingData',second,{'Lines':{'3':{'InPit':True,'Stopped':False}}},99,104)
    assert old['Lines']['3']['InPit'] is False and old['Lines']['3']['Stopped'] is False
    same,changed,duplicate=ledger.apply('TimingData',old,{'Lines':{'3':{'InPit':True,'Stopped':False}}},99,105)
    assert duplicate and not changed and same==old
    assert ledger.provenance('TimingData.Lines.3.InPit',106)['age_seconds']==4
    cleared,_,_=ledger.apply('TimingData',same,{'Lines':{'3':{'Sectors':{'1':{'_deleted':True}}}}},107,108)
    assert cleared['Lines']['3']['Sectors']['1'] is None


def test_undated_reconnect_snapshot_cannot_replace_dated_observation():
    ledger=PatchLedger(7);state,_,_=ledger.apply('T',{}, {'position':1},100,101)
    state,changed,_=ledger.apply('T',state,{'position':9},None,102)
    assert state['position']==1 and not changed

def test_sparse_indexed_slots_and_deleted_key_lists_do_not_shift_sectors():
    from data_sources.public_timing_provider import indexed
    assert indexed({'2':{'Value':'25'}})==[None,None,{'Value':'25'}]
    ledger=PatchLedger(7)
    state,_,_=ledger.apply('T',{}, {'Sectors':[{'Value':'27'},{'Value':'39'},{'Value':'25'}]},100,101)
    removed,_,_=ledger.apply('T',state,{'Sectors':{'_deleted':['1']}},102,103)
    assert indexed(removed['Sectors'])==[{'Value':'27'},None,{'Value':'25'}]
    late,_,_=ledger.apply('T',removed,{'Sectors':{'1':{'Value':'40'}}},99,104)
    assert indexed(late['Sectors'])[1] is None


def test_merge_field_and_dedup_memory_are_bounded():
    ledger=PatchLedger(7,max_ids=4)
    state={}
    for i in range(20):state,_,_=ledger.apply('T',state,{'value':i},i,i+1)
    assert len(ledger.order)==len(ledger.ids)==4
    nested={};point=nested
    for _ in range(34):point['nested']={};point=point['nested']
    with pytest.raises(ValueError,match='nesting'):ledger.apply('T',{},nested,100,101)


def test_live_requires_matching_identity_and_source_freshness_not_socket():
    health=FeedHealth(7,clock=lambda:120);health.request(['TimingData','Position.z'])
    health.transport('WAITING');health.identity='VERIFIED'
    assert health.snapshot()['state']=='WAITING'
    health.observe('TimingData',None)
    assert health.snapshot()['channels']['TimingData']['state']=='PARTIAL'
    health.observe('TimingData',115)
    assert health.snapshot()['state']=='LIVE'
    assert health.snapshot()['capabilities']['positions']=='MISSING'
    assert health.snapshot(now=136)['state']=='STALE'
    health.transport('ACCESS_DENIED')
    assert health.snapshot()['capabilities']['positions']=='UNAUTHORIZED'


def test_session_identity_checks_meeting_season_type_and_utc_offset():
    info=json.loads((Path(__file__).parent/'fixtures/public-sq-keyframe.json').read_text())['SessionInfo']
    expected={'session_key':11379,'meeting_key':1296,'session_name':'Sprint Qualifying','session_type':'Qualifying','date_start':'2026-10-09T12:30:00+00:00'}
    assert validate_identity(info,expected)==(True,None)
    for changed in ({'meeting_key':1295},{'session_key':11384},{'session_name':'Qualifying'},{'date_start':'2025-10-09T12:30:00+00:00'}):
        assert not validate_identity(info,{**expected,**changed})[0]
    assert utc_stamp('2026-10-09T12:30:00') is None


def live_service(monkeypatch):
    service=RaceControlService();now=time.time()
    meta={'session_key':700,'meeting_key':70,'date_start':utc_iso(now-60),'date_end':utc_iso(now+3600),'session_name':'Race','session_type':'Race','live_allowed':True,'replay_allowed':False}
    data={'meta':meta,'drivers':[{'driver_number':3,'code':'VER','name':'Max Verstappen','team':'Red Bull','color':'#123456'}],
          'events':{},'locations':{},'telemetry':{},'track':None,'public_state':{},'public_laps':{},'complete_archive':False,'downloaded_at':utc_iso(now)}
    monkeypatch.setattr(service,'live_datasets',{700:data});monkeypatch.setattr(service,'live',{700:{'status':'WAITING','last_message':None}})
    monkeypatch.setattr(service,'settings',TimingSettings(persistence=False,max_position_samples=5,max_car_samples=3,max_events=4))
    return service,data,now


def test_measured_channels_validate_driver_timestamp_ranges_and_rpm(monkeypatch):
    service,data,now=live_service(monkeypatch)
    service.ingest_public(700,'Position.z',compressed({'Position':[{'Timestamp':utc_iso(now-1),'Entries':{'3':{'X':100,'Y':200},'99':{'X':500,'Y':600}}},{'Timestamp':utc_iso(now+100),'Entries':{'3':{'X':999,'Y':999}}}]}))
    assert data['locations']['3'][0]==pytest.approx([now-1,100,200]) and len(data['locations'])==1
    service.ingest_public(700,'CarData.z',compressed({'Entries':[{'Utc':utc_iso(now-1),'Cars':{'3':{'Channels':{'0':12000,'2':270,'3':7,'4':100,'5':0}}}}]}))
    assert data['telemetry']['3'][0][1:]==[270,7,100,0,None,12000]
    service.ingest_public(700,'CarData.z',compressed({'Entries':[{'Utc':utc_iso(now-.4),'Cars':{'3':{'Channels':{'0':99999,'2':-1}}}}]}))
    assert len(data['telemetry']['3'])==1


def test_late_duplicate_and_future_samples_cannot_advance_live_buffers(monkeypatch):
    service,data,now=live_service(monkeypatch)
    for i in range(12):service.ingest(700,'location',{'driver_number':3,'date':utc_iso(now-20+i),'x':100+i,'y':200})
    assert len(data['locations']['3'])==5
    last=copy.deepcopy(data['locations']['3'])
    service.ingest(700,'location',{'driver_number':3,'date':utc_iso(now-20),'x':900,'y':900})
    assert data['locations']['3']==last
    service.ingest_public(700,'TimingData',{'Lines':{'3':{'Position':'1'}}},utc_iso(now+100))
    assert 'TimingData' not in data['public_state']


def test_current_stint_pit_transitions_and_lap_completion_are_observed(monkeypatch):
    service,data,now=live_service(monkeypatch)
    service.ingest_public(700,'TimingAppData',{'Lines':{'3':{'Stints':[{'Compound':'SOFT','TotalLaps':3}]}}},utc_iso(now-15))
    service.ingest_public(700,'TimingData',{'Lines':{'3':{'Position':'1','InPit':False,'NumberOfLaps':1,'LastLapTime':{'Value':'1:30.000'}}}},utc_iso(now-12))
    assert data['public_laps']=={}
    service.ingest_public(700,'TimingData',{'Lines':{'3':{'NumberOfLaps':2,'LastLapTime':{'Value':'1:29.000'},'Sectors':[{'Value':'28'},{'Value':'35'},{'Value':'26'}],'InPit':True}}},utc_iso(now-10))
    assert len(data['public_laps']['3'])==1 and data['public_laps']['3'][0]['s1']==28
    assert len(data['events']['pit'])==1
    service.ingest_public(700,'TimingData',{'Lines':{'3':{'InPit':True}}},utc_iso(now-9))
    assert len(data['events']['pit'])==1


def test_replay_and_live_data_for_same_key_are_isolated(monkeypatch):
    service,data,now=live_service(monkeypatch)
    archive={'complete_archive':True,'locations':{'3':[[now-1,800,900]]}}
    monkeypatch.setattr(service,'datasets',{700:archive})
    service.ingest(700,'location',{'driver_number':3,'date':utc_iso(now-1),'x':100,'y':200})
    assert archive['locations']['3'][0][1:]==[800,900]
    assert service.live_data(700) is data
    monkeypatch.setattr(service,'live_datasets',{})
    assert service.live_data(700) is None


def test_checkpoint_recovery_is_stale_matches_context_and_does_not_contain_secrets(tmp_path):
    meta={'session_key':7,'meeting_key':70,'session_name':'Race','date_start':'2026-10-11T12:00:00+00:00'}
    data={'meta':meta,'drivers':[],'events':{},'locations':{},'telemetry':{},'track':None,'secret':'do not persist','_client':'do not persist'}
    store=TimingCheckpointStore(tmp_path);store.save(data,{'state':'LIVE','capabilities':{}})
    saved=store.load(meta)
    assert saved['data']['recovered'] and saved['diagnostics']['state']=='STALE'
    assert 'secret' not in saved['data'] and '_client' not in saved['data']
    assert store.load({**meta,'meeting_key':71}) is None
    store.path(7).write_bytes(b'bad gzip');assert store.load(meta) is None


@pytest.mark.parametrize('fraction,expected',[(.1,[6,4,3,2,1]),(.25,[13,10,8,6,5,4,3,2,1]),(.5,[19,14,12,10,8,6,4,3,2,1]),(.75,[25,18,15,12,10,8,6,4,2,1])])
def test_fia_2026_shortened_race_points(fraction,expected):assert points_table(2026,completion=fraction,green_laps=2)==expected


def test_sprint_scoring_and_unknown_green_laps():
    assert points_table(2021,sprint=True)==[3,2,1]
    assert points_table(2026,sprint=True,completion=.49,green_laps=2)==[]
    assert points_table(2026,sprint=True,completion=.5,green_laps=2)==[8,7,6,5,4,3,2,1]
    assert points_table(2026,completion=.9,green_laps=None) is None
    assert points_table(2026,completion=.9,green_laps=1)==[]


def projection_frame(race_field,sprint=False):
    return {'at':utc_stamp('2025-05-01T12:00:00+00:00'),'racing':True,'meta':{'session_key':7,'session_name':'Sprint' if sprint else 'Race'},
            'rows':[{'driver_number':i,'code':f'D{i}','name':f'Pilot {i}','position':i,'lap':10,'status':None,'best_lap':None} for i in range(1,13)]}


def test_projection_excludes_future_results_and_adds_weekend_sprint_once(race_field):
    frame=projection_frame(race_field)
    with SessionLocal.begin() as db:db.add(SprintResult(race_id=race_field['target'],driver_id=1,constructor_id=1,position=1,points=8,available_at='2025-04-01T12:00:00+00:00'))
    gp=RaceControlProjectionService().project(race_field['target'],frame)
    leader=next(r for r in gp['drivers'] if r['driver_id']==1)
    assert leader['official_points']==56 and leader['session_points']==25 and leader['projected_points']==81
    sprint=RaceControlProjectionService().project(race_field['target'],projection_frame(race_field,True))
    leader=next(r for r in sprint['drivers'] if r['driver_id']==1)
    assert leader['official_points']==48 and leader['session_points']==8
    assert not gp['official_standings_modified']


def test_projection_dsq_and_classified_retirement_and_constructor_sum(race_field):
    frame=projection_frame(race_field);frame['rows'][0]['status']='DSQ';frame['rows'][1].update(status='DNF',lap=9)
    frame['rows'][2].update(status='DNF',lap=8)
    p=RaceControlProjectionService().project(race_field['target'],frame)
    rows={r['driver_id']:r for r in p['drivers']}
    assert rows[1]['session_points']==0 and rows[2]['session_points']==18 and rows[3]['session_points']==0
    team=next(r for r in p['constructors'] if r['constructor_id']==1)
    assert team['session_points']==18
    stopped=RaceControlProjectionService().project(race_field['target'],frame,'STOPPED_NOW')
    assert stopped['status']=='UNVERIFIED_STOPPAGE_RULES' and all(r['projected_points'] is None for r in stopped['drivers'])

def test_projection_uses_completed_laps_and_explicit_retirement_report(race_field):
    frame=projection_frame(race_field);frame['rows'][0]['completed_laps']=10
    frame['rows'][1].update(lap=9,completed_laps=8,condition={'retired':True})
    p=RaceControlProjectionService().project(race_field['target'],frame)
    retired=next(r for r in p['drivers'] if r['driver_id']==2)
    assert retired['session_points']==0 # entering lap nine does not complete it


def test_retry_budget_and_access_denied_do_not_spin(monkeypatch):
    feed=PublicTimingFeed(7,lambda *args:None,lambda *args:None)
    calls=[]
    def denied():calls.append(1);feed.status('ACCESS_DENIED','HTTP 403')
    monkeypatch.setattr(feed,'connect_once',denied);feed.supervise()
    assert calls==[1] and feed.health.snapshot()['state']=='ACCESS_DENIED'

def test_reconnect_failure_budget_and_delays_are_bounded(monkeypatch):
    from dataclasses import replace
    feed=PublicTimingFeed(7,lambda *args:None,lambda *args:None)
    feed.settings=replace(feed.settings,max_attempts=3);delays=[];attempts=[]
    class NoSleep:
        def is_set(self):return False
        def wait(self,delay):delays.append(delay);return False
    feed.cancel=NoSleep()
    def failed():attempts.append(1);raise OSError('Synthetic transport outage')
    monkeypatch.setattr(feed,'connect_once',failed);feed.supervise()
    assert len(attempts)==3 and feed.health.snapshot()['state']=='PROVIDER_UNAVAILABLE'
    assert all(base<=delay<=base+.5 for base,delay in zip((1,2,4),delays))

def test_late_or_future_identity_patch_does_not_invalidate_current_session():
    health=FeedHealth(7,clock=lambda:1000)
    feed=PublicTimingFeed(7,lambda *args:None,lambda *args:None,health=health)
    feed.receive('SessionInfo',{'Key':7},utc_iso(990))
    feed.receive('SessionInfo',{'Key':6},utc_iso(980))
    feed.receive('SessionInfo',{'Key':6},utc_iso(1100))
    assert feed.accepted and feed.identity['Key']==7


def test_duplicate_start_is_one_supervisor(monkeypatch):
    feed=PublicTimingFeed(7,lambda *args:None,lambda *args:None)
    class Running:
        def is_alive(self):return True
    feed.thread=Running()
    assert feed.start() is feed


def test_settings_refuse_untested_providers_and_invalid_threshold(monkeypatch):
    monkeypatch.setenv('LIVE_STALE_THRESHOLD_SECONDS','nan')
    with pytest.raises(ValueError,match='THRESHOLD'):TimingSettings.environment()
    monkeypatch.setenv('LIVE_STALE_THRESHOLD_SECONDS','20');monkeypatch.setenv('LIVE_SECONDARY_PROVIDER','unverified')
    with pytest.raises(ValueError,match='secondary'):TimingSettings.environment()


def test_dated_weather_validates_ranges_and_does_not_refresh_unchanged_fields(monkeypatch):
    service,data,now=live_service(monkeypatch)
    service.ingest_public(700,'WeatherData',{'AirTemp':'29','TrackTemp':'42','Humidity':'400','Rainfall':'0'},utc_iso(now-30))
    service.ingest_public(700,'WeatherData',{'AirTemp':'30'},utc_iso(now-1))
    weather=data['events']['weather'][-1]
    assert weather['air_temperature']==30 and weather['track_temperature'] is None and weather['humidity'] is None
    assert weather['rainfall'] is None # absent update is not a fresh no-rain observation

def test_protocol_utc_fields_without_suffix_are_explicitly_normalized(monkeypatch):
    service,data,now=live_service(monkeypatch)
    known_utc=datetime.fromtimestamp(now-1,timezone.utc).replace(tzinfo=None).isoformat()
    assert utc_stamp(known_utc) is None
    service.ingest_public(700,'RaceControlMessages',{'Messages':[{'Utc':known_utc,'Message':'YELLOW','Flag':'YELLOW','Scope':'Track'}]})
    assert data['events']['race_control'][0]['date'].endswith('+00:00')
    assert service.feed_health(700).snapshot()['channels']['RaceControlMessages']['state']=='AVAILABLE'
    service.ingest_public(700,'CarData.z',compressed({'Entries':[{'Utc':known_utc,'Cars':{'3':{'Channels':{'2':240}}}}]}))
    assert data['telemetry']['3'][0][1]==240


def test_timingstats_best_sectors_are_aggregates_not_fake_completed_laps(monkeypatch):
    from services.race_control_service import TimingTimeline
    service,data,now=live_service(monkeypatch)
    service.ingest_public(700,'TimingStats',{'Lines':{'3':{'PersonalBestLapTime':{'Value':'1:30.000'},'BestSectors':{'0':{'Value':'28'},'2':{'Value':'26'}}}}},utc_iso(now-1))
    frame=service.public_frame(data,TimingTimeline.frame(data,now,3),3)
    assert frame['personal_best']==[28,None,26] and frame['laps']==[] and frame['ideal_lap'] is None
    assert frame['selected']['best_lap']==90

def test_empty_or_foreign_timing_patch_cannot_turn_a_socket_into_live(monkeypatch):
    service,data,now=live_service(monkeypatch)
    health=service.feed_health(700);health.identity='VERIFIED';health.transport('WAITING')
    service.ingest_public(700,'TimingData',{'Lines':{}},utc_iso(now-2))
    service.ingest_public(700,'TimingData',{'Lines':{'999':{'Position':'1'}}},utc_iso(now-1))
    assert health.snapshot()['state']=='WAITING'
    service.ingest_public(700,'TimingData',{'Lines':{'3':{'Position':'1'}}},utc_iso(now-.5))
    assert health.snapshot()['state']=='LIVE'


def test_diagnostics_routes_keep_race_control_namespace_and_do_not_restore_platform(monkeypatch):
    from app import create_app
    from api.race_control_routes import service
    monkeypatch.setattr(service,'session',lambda *args:{'session_key':700,'meeting_key':70,'session_name':'Race','date_start':'2026-10-11T12:00:00+00:00'})
    monkeypatch.setattr(service,'live',{});monkeypatch.setattr(service,'settings',TimingSettings(persistence=False))
    client=create_app().test_client()
    response=client.get('/race-control/1/700/diagnostics')
    assert response.status_code==200 and response.json['state']=='DISCONNECTED'
    assert client.get('/race-control/1/700/capabilities').json['capabilities']['positions']=='MISSING'
    assert client.get('/race-control/providers').status_code==200
    assert client.get('/api/live/sessions').status_code==404
