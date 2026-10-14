"""Completion regressions; synthetic evidence never certifies an upstream live feed."""
import copy,gzip,json,os,time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import pytest
from data_sources.timing_contract import FeedHealth,utc_iso,utc_stamp,validate_identity
from services.race_control_checkpoint import TimingCheckpointStore
from services.race_control_projection_service import RaceControlProjectionService,points_table
from services.race_control_results import confirm_result
from services.race_control_service import TimingTimeline
from database.db import SessionLocal
from models.weekend import WeekendSessionSnapshot
from models.race import Race
from models.race_result import RaceResult
from models.analytics import RaceEntry
from test_timing_integration import live_service,projection_frame


def publish(rid,when,code='R',winner=1):
    rows=[{'driver_id':i,'driver_code':f'D{i}','constructor_id':(i+1)//2,'position':1 if i==winner else i+1 if i<winner else i,'points':25 if i==winner else 0} for i in range(1,13)]
    with SessionLocal.begin() as db:db.add(WeekendSessionSnapshot(race_id=rid,session=code,source='jolpica',source_url='https://api.jolpi.ca/ergast/f1/',session_start_at='2025-03-01T14:00:00+00:00',session_end_at='2025-03-01T16:00:00+00:00',observed_at=when,content_hash=when+str(winner),data=rows))


def result_frame(race_field):
    f=projection_frame(race_field);f.update(phase='FINISHED');f['meta'].update(code='R');return f


def test_signalr_finalised_is_only_provisional(monkeypatch,race_field):
    service,data,now=live_service(monkeypatch)
    data['public_state']={'SessionInfo':{'SessionStatus':'Finalised'},'SessionStatus':{'Status':'Finalised'},'TimingData':{'Lines':{'3':{'Position':'1'}}}}
    f=service.public_frame(data,TimingTimeline.frame(data,now,3),3)
    assert f['phase']=='FINISHED' and f['winner'] is None
    f=result_frame(race_field);assert confirm_result(72,f,'LIVE')['status']=='PROVISIONAL_P1' and f['winner'] is None


def test_published_result_changes_winner_after_penalty_and_not_before_cutoff(race_field):
    publish(72,'2025-04-15T12:00:00+00:00',winner=1)
    publish(72,'2025-05-02T12:00:00+00:00',winner=2)
    f=result_frame(race_field);assert confirm_result(72,f,'LIVE')['status']=='OFFICIAL_WINNER_CONFIRMED';assert f['winner']['code']=='D1'
    f['at']=utc_stamp('2025-05-03T12:00:00+00:00');assert confirm_result(72,f,'LIVE')['winner']['code']=='D2'


@pytest.mark.parametrize('phase',['WAITING','RUNNING','SUSPENDED','BREAK','FINISHING'])
def test_published_result_cannot_announce_winner_before_finish(race_field,phase):
    publish(72,'2025-04-15T12:00:00+00:00');f=result_frame(race_field);f['phase']=phase
    assert not confirm_result(72,f,'REPLAY')['winner_confirmed'] and f['winner'] is None


def test_cancelled_session_has_no_winner(race_field):
    publish(72,'2025-04-15T12:00:00+00:00')
    with SessionLocal.begin() as db:db.get(Race,72).race_status='CANCELLED'
    f=result_frame(race_field);assert confirm_result(72,f,'LIVE')['status']=='SESSION_CANCELLED'


def test_unpublished_live_result_and_explicit_verified_historical_outcome(race_field):
    publish(72,'2025-05-02T12:00:00+00:00')
    f=result_frame(race_field);assert confirm_result(72,f,'LIVE')['status']=='PROVISIONAL_P1'
    evidence=confirm_result(72,f,'REPLAY');assert evidence['verification_scope']=='HISTORICAL_LATEST' and f['winner']['code']=='D1'


def test_legacy_prior_results_cannot_supply_replay_baseline(race_field):
    f=projection_frame(race_field);f['mode']='REPLAY'
    p=RaceControlProjectionService().project(72,f)
    assert p['status']=='UNVERIFIED_BASELINE' and all(r['projected_points'] is None for r in p['drivers'])


def test_result_correction_after_cutoff_excluded_and_team_change_preserved(race_field):
    publish(90,'2025-03-20T12:00:00+00:00');publish(4,'2025-04-02T12:00:00+00:00')
    publish(4,'2025-05-02T12:00:00+00:00',winner=2)
    with SessionLocal.begin() as db:db.query(RaceEntry).filter_by(race_id=72,driver_id=1).one().constructor_id=6
    f=projection_frame(race_field);f['mode']='REPLAY';p=RaceControlProjectionService().project(72,f)
    d=next(r for r in p['drivers'] if r['driver_id']==1);assert d['official_points']==50 and d['team']=='Team 6' and d['projected_points']==75
    c=next(r for r in p['constructors'] if r['constructor_id']==6);assert c['session_points']==25 and c['official_points']==0


def test_missing_mapping_withholds_aggregate_totals(race_field):
    f=projection_frame(race_field);f['rows'][0].update(name='Unknown',code='XYZ')
    p=RaceControlProjectionService().project(72,f);assert p['status']=='PARTIAL' and all(r['projected_points'] is None for r in p['drivers'])


@pytest.mark.parametrize('year,bonus',[(2024,1),(2025,0),(2026,0)])
def test_fastest_lap_points_and_dns_zero(race_field,year,bonus):
    with SessionLocal.begin() as db:db.get(Race,72).season_year=year
    f=projection_frame(race_field)
    for i,r in enumerate(f['rows']):r['best_lap']=90+i
    f['rows'][11]['status']='DNS';p=RaceControlProjectionService().project(72,f)
    assert next(r for r in p['drivers'] if r['driver_id']==1)['session_points']==25+bonus
    assert next(r for r in p['drivers'] if r['driver_id']==12)['session_points']==0


def test_dead_heat_shares_occupied_slots(race_field):
    f=projection_frame(race_field);f['rows'][1]['position']=1;p=RaceControlProjectionService().project(72,f)
    assert all(next(r for r in p['drivers'] if r['driver_id']==i)['session_points']==21.5 for i in (1,2))


def test_historical_stoppage_requirements_and_unsupported_season(race_field):
    assert points_table(2021,completion=.5,green_laps=2) is None
    assert points_table(2008) is None and points_table(2027) is None
    with SessionLocal.begin() as db:db.get(Race,72).season_year=2022
    f=projection_frame(race_field);f.update(scheduled_laps=20,laps_for_projection={'1':[{'lap':1,'complete':True,'track_flag':'GREEN'},{'lap':2,'complete':True,'track_flag':'GREEN'}]})
    assert RaceControlProjectionService().project(72,f,'STOPPED_NOW')['status']=='UNVERIFIED_STOPPAGE_RULES'


def test_checkpoint_concurrent_writes_corruption_limits_old_and_future(tmp_path):
    store=TimingCheckpointStore(tmp_path);meta={'session_key':7,'meeting_key':70,'session_type':'Race','session_name':'Race','date_start':'2025-01-01T12:00:00+00:00'}
    data={'meta':meta,'events':{},'locations':{},'telemetry':{}}
    with ThreadPoolExecutor(6) as pool:list(pool.map(lambda i:store.save({**data,'public_state':{'count':i}},{'state':'LIVE','Authorization':'secret-test-token'}),range(30)))
    assert store.load(meta)['diagnostics']['state']=='STALE'
    assert 'Authorization' not in json.loads(gzip.decompress(store.path(7).read_bytes()))['diagnostics']
    assert store.load({**meta,'session_type':'Qualifying'}) is None
    original=store.path(7).read_bytes();saved=json.loads(gzip.decompress(original));saved['saved_at']=time.time()+100
    store.path(7).write_bytes(gzip.compress(json.dumps(saved).encode()));assert store.load(meta) is None
    store.path(7).write_bytes(original);os.utime(store.path(7),(0,0));assert store.load(meta) is None
    store.max_bytes=100
    with pytest.raises(ValueError):store.save(data,{})
    store.path(7).write_bytes(gzip.compress(b'x'*101));assert store.load(meta) is None
    store.path(7).write_bytes(b'broken');assert store.load(meta) is None
    assert not list(tmp_path.glob('*.tmp'))


def test_heartbeat_only_transport_does_not_refresh_timing():
    health=FeedHealth(7,clock=lambda:100);health.identity='VERIFIED';health.observe('TimingData',90,91)
    health.transport('CONNECTED');a=health.snapshot(now=120);health.transport('CONNECTED');b=health.snapshot(now=120)
    assert a['state']==b['state']=='STALE' and a['last_valid_observation_utc']==b['last_valid_observation_utc'] and a['last_received_packet_utc']==b['last_received_packet_utc']


def test_restart_matching_fresh_timing_clears_stale_recovery(monkeypatch):
    service,data,now=live_service(monkeypatch);h=service.feed_health(700);h.recovered=True;h.identity='VERIFIED';h.transport('WAITING')
    service.ingest_public(700,'TimingData',{'Lines':{'3':{'Position':'1'}}},utc_iso(now-60));assert h.snapshot()['state']=='STALE'
    service.ingest_public(700,'TimingData',{'Lines':{'3':{'Position':'2'}}},utc_iso(now-1));assert h.snapshot()['state']=='LIVE'


def test_delayed_start_same_identity_and_restarted_transport_accepts_same_context():
    import json
    from pathlib import Path
    info=json.loads((Path(__file__).parent/'fixtures/public-sq-keyframe.json').read_text())['SessionInfo']
    expected={'session_key':11379,'meeting_key':1296,'session_name':'Sprint Qualifying','session_type':'Qualifying','date_start':'2026-10-09T12:30:00+00:00'}
    delayed={**info,'StartDate':'2026-10-09T20:40:00'}
    assert validate_identity(delayed,expected)[0]
    assert validate_identity(info,expected)[0] # interruption does not change session identity
    assert not validate_identity({**info,'Type':'Race'},expected)[0]


def test_versioned_sprint_counted_once_and_unpublished_version_excluded(race_field):
    publish(90,'2025-03-20T12:00:00+00:00');publish(4,'2025-04-02T12:00:00+00:00')
    publish(72,'2025-04-25T12:00:00+00:00',code='SPRINT')
    with SessionLocal.begin() as db:
        snapshot=db.query(WeekendSessionSnapshot).filter_by(race_id=72,session='SPRINT').one();rows=copy.deepcopy(snapshot.data);rows[0]['points']=8;snapshot.data=rows
    f=projection_frame(race_field);f['mode']='REPLAY';gp=RaceControlProjectionService().project(72,f)
    assert next(r for r in gp['drivers'] if r['driver_id']==1)['official_points']==58
    f['meta']['session_name']='Sprint';sprint=RaceControlProjectionService().project(72,f)
    assert next(r for r in sprint['drivers'] if r['driver_id']==1)['official_points']==50
    with SessionLocal.begin() as db:db.query(WeekendSessionSnapshot).filter_by(race_id=72,session='SPRINT').one().observed_at='2025-05-02T12:00:00+00:00'
    f['meta']['session_name']='Race';p=RaceControlProjectionService().project(72,f)
    assert next(r for r in p['drivers'] if r['driver_id']==1)['official_points']==50


def test_duplicate_packet_does_not_change_measured_source_receipt_latency():
    h=FeedHealth(7,clock=lambda:120);h.observe('TimingData',100,101)
    assert h.snapshot()['channels']['TimingData']['latency_seconds']==1
    h.observe('TimingData',100,119,duplicate=True)
    c=h.snapshot()['channels']['TimingData'];assert c['latency_seconds']==1 and c['last_received_utc']==utc_iso(119)


def test_car_brake_false_zero_partial_and_malformed_channels(monkeypatch):
    from test_timing_integration import compressed
    service,data,now=live_service(monkeypatch)
    service.ingest_public(700,'CarData.z',compressed({'Entries':[{'Utc':utc_iso(now-2),'Cars':{'3':{'Channels':{'2':0,'3':0,'4':0,'5':False,'45':0}}}}]}))
    assert data['telemetry']['3'][0][1:]==[0,0,0,0,0,None]
    service.ingest_public(700,'CarData.z',compressed({'Entries':[{'Utc':utc_iso(now-1),'Cars':{'3':{'Channels':[]}}}]}))
    assert len(data['telemetry']['3'])==1
    service.ingest_public(700,'CarData.z',compressed({'Entries':[{'Utc':utc_iso(now-.2),'Cars':{'3':{'Channels':{'2':200,'3':2.5}}}}]}))
    assert data['telemetry']['3'][-1][2] is None


def test_previous_session_envelope_and_embedded_samples_rejected(monkeypatch):
    from test_timing_integration import compressed
    service,data,now=live_service(monkeypatch)
    service.ingest_public(700,'TimingData',{'Lines':{'3':{'Position':'1'}}},utc_iso(now-7200))
    assert 'TimingData' not in data['public_state']
    service.ingest_public(700,'Position.z',compressed({'Position':[{'Timestamp':utc_iso(now-7200),'Entries':{'3':{'X':100,'Y':200}}}]}))
    assert not data['locations']
    service.ingest_public(700,'CarData.z',compressed({'Entries':[{'Utc':utc_iso(now-7200),'Cars':{'3':{'Channels':{'2':250}}}}]}))
    assert not data['telemetry']
