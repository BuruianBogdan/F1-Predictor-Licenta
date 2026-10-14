import copy
from datetime import datetime,timezone,timedelta
import pytest
from services.race_control_service import TimingTimeline,RaceControlService,stamp,make_track
from data_sources.race_control_provider import RaceControlProvider

START='2026-10-09T08:30:00+00:00'
T=stamp(START)
def date(seconds):return datetime.fromtimestamp(T+seconds,timezone.utc).isoformat()
@pytest.fixture
def timeline():
    return {'meta':{'session_key':100,'date_start':START,'date_end':date(300),'session_type':'Practice'},'drivers':[{'driver_number':63,'code':'RUS','name':'George Russell','team':'Mercedes','color':'#00ccaa','image':'/image'},{'driver_number':3,'code':'VER','name':'Max Verstappen','team':'Red Bull','color':'#1122ff','image':'/image'}], 'events':{'laps':[{'driver_number':63,'lap_number':1,'date_start':date(0),'duration_sector_1':30,'duration_sector_2':31,'duration_sector_3':32,'lap_duration':93,'is_pit_out_lap':False},{'driver_number':3,'lap_number':1,'date_start':date(0),'duration_sector_1':29,'duration_sector_2':30,'duration_sector_3':31,'lap_duration':90,'is_pit_out_lap':False}], 'race_control':[{'date':date(0),'message':'SESSION STARTED','category':'SessionStatus'},{'date':date(0),'flag':'GREEN','scope':'Track','message':'GREEN'}], 'position':[{'date':date(94),'driver_number':3,'position':1},{'date':date(94),'driver_number':63,'position':2}], 'weather':[{'date':date(15),'rainfall':0,'wind_speed':2,'track_temperature':42}], 'stints':[{'driver_number':63,'lap_start':1,'lap_end':5,'compound':'SOFT','tyre_age_at_start':2}], 'session_result':[{'driver_number':63,'position':1},{'driver_number':3,'position':2}]},'locations':{},'telemetry':{},'track':None,'complete_archive':True,'downloaded_at':START}

def test_sectors_appear_only_when_completed_and_no_future_best_lap(timeline):
    early=TimingTimeline.frame(timeline,T+29,63)
    assert early['laps'][0]['s1'] is None and early['rows'][0]['best_lap'] is None
    assert early['session_best']==[{'time':29,'driver_number':3},None,None]
    mid=TimingTimeline.frame(timeline,T+61,63)
    assert mid['laps'][0]['s1']==30 and mid['laps'][0]['s2']==31 and mid['laps'][0]['s3'] is None
    assert mid['selected']['best_lap'] is None and mid['winner'] is None
    late=TimingTimeline.frame(timeline,T+94,63)
    assert late['selected']['best_lap']==93 and late['ideal_lap']==93
    assert late['selected']['gap']==3

def test_weather_is_not_shown_before_observation_and_no_invented_wetness(timeline):
    assert TimingTimeline.frame(timeline,T+5,63)['weather'] is None
    f=TimingTimeline.frame(timeline,T+20,63)
    assert f['surface']=='NO RAIN DETECTED'
    assert f['rain_risk'] is None

def test_each_local_yellow_must_clear_individually(timeline):
    timeline['events']['race_control'] += [{'date':date(10),'flag':'YELLOW','scope':'Sector','sector':5,'message':'YELLOW'},{'date':date(11),'flag':'DOUBLE YELLOW','scope':'Sector','sector':6,'message':'DOUBLE YELLOW'},{'date':date(12),'flag':'CLEAR','scope':'Sector','sector':5,'message':'CLEAR'},{'date':date(13),'flag':'CLEAR','scope':'Sector','sector':6,'message':'CLEAR'}]
    assert TimingTimeline.frame(timeline,T+12,63)['hazard_sectors']=={'6':'DOUBLE YELLOW'}
    assert TimingTimeline.frame(timeline,T+12,63)['flag']=='YELLOW'
    assert TimingTimeline.frame(timeline,T+13,63)['flag']=='GREEN'

def test_deleted_lap_is_removed_when_deletion_is_announced(timeline):
    timeline['events']['race_control'].append({'date':date(100),'message':'CAR 3 (VER) TIME 1:30.000 DELETED - TRACK LIMITS AT TURN 2 LAP 1'})
    assert TimingTimeline.frame(timeline,T+95,3)['selected']['best_lap']==90
    f=TimingTimeline.frame(timeline,T+101,3)
    assert f['selected']['best_lap'] is None and f['laps'][0]['deleted']
    assert f['session_best'][0]=={'time':30,'driver_number':63}

def test_qualifying_order_uses_provider_phase_positions(timeline):
    timeline['meta']['session_type']='Qualifying'
    timeline['events']['position']=[{'date':date(94),'driver_number':63,'position':1},{'date':date(94),'driver_number':3,'position':2}]
    f=TimingTimeline.frame(timeline,T+95,63)
    assert f['rows'][0]['code']=='RUS' # quicker earlier-phase lap does not promote an eliminated car
    assert f['selected']['interval'] is None

def test_race_gaps_are_not_best_lap_differences(timeline):
    timeline['meta']['session_type']='Race'
    timeline['events']['intervals']=[{'date':date(95),'driver_number':63,'gap_to_leader':2.123,'interval':1.202}]
    assert TimingTimeline.frame(timeline,T+94,63)['selected']['gap'] is None
    f=TimingTimeline.frame(timeline,T+95,63)
    assert f['selected']['gap']==2.123 and f['selected']['interval']==1.202

def test_final_winner_waits_for_session_finished_and_classification(timeline):
    timeline['events']['race_control'] += [{'date':date(290),'message':'CHEQUERED FLAG','flag':'CHEQUERED','scope':'Track'},{'date':date(310),'message':'SESSION FINISHED','category':'SessionStatus'}]
    assert TimingTimeline.frame(timeline,T+300,63)['winner'] is None
    assert TimingTimeline.frame(timeline,T+310,63)['winner']['code']=='RUS'
    timeline['events']['session_result']=[]
    assert TimingTimeline.frame(timeline,T+310,63)['winner'] is None

def test_unknown_lap_start_does_not_leak_final_sectors(timeline):
    timeline['events']['laps'][0]['date_start']=None
    f=TimingTimeline.frame(timeline,T+94,63)
    assert f['laps']==[] and f['selected']['best_lap'] is None

def test_missing_values_do_not_become_zero(timeline):
    timeline['events']['laps'][0]['duration_sector_2']=None
    timeline['events']['laps'][0]['lap_duration']=None
    f=TimingTimeline.frame(timeline,T+100,63)
    assert f['laps'][0]['s2'] is None and f['laps'][0]['s3'] is None
    assert f['ideal_lap'] is None

def test_session_identity_cannot_mix_races(monkeypatch):
    monkeypatch.setattr(RaceControlService,'catalog',lambda self,rid:{'sessions':[{'session_key':100}]})
    with pytest.raises(ValueError,match='does not belong'):RaceControlService().session(1,101)

def test_no_live_before_start_or_without_access(monkeypatch):
    monkeypatch.setattr(RaceControlService,'session',lambda *args:{'session_key':100,'live_allowed':False,'replay_allowed':False})
    with pytest.raises(ValueError,match='opens at'):RaceControlService().prepare(1,100,'LIVE')
    with pytest.raises(ValueError,match='live access window'):RaceControlService().prepare(1,100,'REPLAY')

def test_catalog_matches_gp_date_and_meeting_not_similar_country_names(race_field,monkeypatch):
    service=RaceControlService();race,_=service.race_info(race_field['target']);day=race['date']
    rows=[{'session_key':1,'meeting_key':20,'session_name':'Race','session_type':'Race','date_start':day+'T14:00:00+00:00','date_end':day+'T16:00:00+00:00'},{'session_key':2,'meeting_key':20,'session_name':'Practice 1','session_type':'Practice','date_start':day+'T10:00:00+00:00','date_end':day+'T11:00:00+00:00'},{'session_key':3,'meeting_key':99,'session_name':'Practice 1','date_start':day+'T10:00:00+00:00','date_end':day+'T11:00:00+00:00'}]
    monkeypatch.setattr(service.provider,'fetch',lambda *args,**kwargs:rows)
    result=service.catalog(race_field['target'],refresh=True)
    assert {r['session_key'] for r in result['sessions']}=={1,2}
    assert not any(k in str(result).lower() for k in ('access_token','password'))

def test_car_locations_preserve_real_coordinates_and_drop_unknown_origin():
    positions=RaceControlService().compact_locations([{'date':date(0),'driver_number':63,'x':0,'y':0},{'date':date(.1),'driver_number':63,'x':120,'y':-35},{'date':date(.7),'driver_number':63,'x':190,'y':-10}])
    assert positions['63']==[[T+.1,120,-35],[T+.7,190,-10]]

def test_live_buffer_cannot_masquerade_as_complete_archive(timeline,monkeypatch):
    service=RaceControlService();timeline['complete_archive']=False
    monkeypatch.setattr(service,'session',lambda *args:{'replay_allowed':True})
    monkeypatch.setattr(service,'load',lambda key:timeline)
    with pytest.raises(ValueError,match='complete replay'):service.frame(1,100,T+95,63,'REPLAY')

def test_published_deletion_matches_time_when_source_lap_numbers_differ(timeline):
    timeline['events']['laps'].append({'driver_number':3,'lap_number':2,'date_start':date(100),'lap_duration':89,'duration_sector_1':28,'duration_sector_2':30,'duration_sector_3':31})
    timeline['events']['race_control'].append({'date':date(200),'message':'CAR 3 (VER) TIME 1:30.000 DELETED - TRACK LIMITS AT TURN 2 LAP 2'})
    f=TimingTimeline.frame(timeline,T+201,3)
    assert f['selected']['best_lap']==89 # the valid lap 2 must not be deleted
    assert next(l for l in f['laps'] if l['lap']==1)['deleted']
    assert not next(l for l in f['laps'] if l['lap']==2)['deleted']

def test_public_signalr_sparse_sector_patches_keep_unchanged_fields():
    from data_sources.public_timing_provider import merge_patch,indexed
    initial={'Sectors':[{'Value':'27.100'},{'Value':'39.200'},{'Value':''}]}
    patched=merge_patch(initial,{'Sectors':{'2':{'Value':'25.800','PersonalFastest':True}}})
    assert [r['Value'] for r in indexed(patched['Sectors'])]==['27.100','39.200','25.800']
    assert initial['Sectors'][2]['Value']==''

def test_public_feed_ignores_previous_session_before_accepting_current():
    from data_sources.public_timing_provider import PublicTimingFeed
    received=[];statuses=[]
    feed=PublicTimingFeed(100,lambda *args:received.append(args),lambda *args:statuses.append(args))
    feed.receive('SessionInfo',{'Key':99});feed.receive('TimingData',{'Lines':{}})
    assert not received and not feed.ready.is_set()
    feed.receive('SessionInfo',{'Key':100});feed.receive('DriverList',{'63':{'Tla':'RUS'}})
    assert feed.ready.is_set() and len(received)==2

def test_actual_free_public_snapshot_has_real_sprint_qualifying_order(monkeypatch,timeline):
    import json
    from pathlib import Path
    service=RaceControlService();data=copy.deepcopy(timeline);data.update(public_state={},public_laps={},source='Formula 1 public SignalR');key=100
    monkeypatch.setattr(service,'live_datasets',{key:data});monkeypatch.setattr(service,'live',{key:{'last_message':None}})
    fixture=json.loads((Path(__file__).parent/'fixtures/public-sq-keyframe.json').read_text())
    for topic,patch in fixture.items():service.ingest_public(key,topic,patch)
    f=service.public_frame(data,TimingTimeline.frame(data,T+300,3),3)
    assert len(f['rows'])==2 and f['rows'][0]['code']=='VER'
    assert f['selected']['best_lap']==91.156
    assert not f['positions_available'] and not f['telemetry_available']
    assert f['laps']==[] # a snapshot does not contain a trustworthy full lap history

def test_delayed_session_uses_actual_end_and_reloads_incomplete_position_coverage(timeline):
    from services.race_control_service import time_extent
    timeline['events']['race_control']=[{'date':date(100),'message':'SESSION STARTED'},{'date':date(1000),'message':'SESSION FINISHED'}]
    timeline['coverage_end']=T+600 # old schedule would have truncated the race
    start,end=time_extent(timeline)
    assert (start,end)==(T+100,T+1000)
    assert not RaceControlService().covered(timeline)
    assert TimingTimeline.frame(timeline,T+1001,63)['winner']['code']=='RUS'
    timeline['coverage_end']=T+1300
    assert RaceControlService().covered(timeline)

def test_driver_portrait_identity_does_not_confuse_reused_ver_code():
    from database.db import SessionLocal
    from models.driver import Driver
    from models.analytics import DriverMedia
    with SessionLocal.begin() as db:
        db.add(Driver(driver_id=1,driver_ref='max_verstappen',forename='Max',surname='Verstappen',code='VER'))
        db.add(Driver(driver_id=2,driver_ref='vergne',forename='Jean-Eric',surname='Vergne',code='VER'))
        db.flush();db.add(DriverMedia(driver_id=1,image_url='https://example.test/max.webp',source='fixture'))
    row=RaceControlService().enrich_drivers([{'driver_number':3,'name_acronym':'VER','first_name':'Max','last_name':'Verstappen','team_colour':'4781D7'}])[0]
    assert row['image']=='https://example.test/max.webp'
