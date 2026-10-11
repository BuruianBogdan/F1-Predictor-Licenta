import copy
from datetime import datetime,timezone,timedelta
import pytest
from services.race_strategy_service import RaceStrategyService,colour
from services.race_control_service import TimingTimeline,stamp

BASE=datetime(2026,10,4,8,33,tzinfo=timezone.utc)
def date(t):return (BASE+timedelta(seconds=t)).isoformat()
@pytest.fixture
def situation():
    rows=[];history={}
    for number,pos,gap,age in [(3,1,0.,23),(63,2,5.,23),(16,3,12.,12)]:
        rows.append({'driver_number':number,'code':str(number),'name':str(number),'color':'#abcdef','position':pos,'lap':45,'gap':gap,'compound':'MEDIUM','tyre_age':age,'tyre_age_at_start':0,'stint_start_lap':45-age,'in_pit':False,'status':None})
        history[number]=[{'lap':i,'complete':True,'time':100+.035*(i-(45-age)),'date_start':date((i-39)*110),'deleted':False,'pit_out':False} for i in range(40,45)]
    frame={'at':stamp(date(800)),'phase':'RUNNING','flag':'GREEN','racing':True,'rows':rows,'selected':rows[1],'winner':None,'weather':{'track_temperature':35},'_controls':[{'date':date(0),'flag':'GREEN','scope':'Track','message':'GREEN'}],'_laps_by':history,'_pits_by':{}}
    data={'meta':{'session_name':'Race','circuit_short_name':'Test'},'events':{}}
    return frame,data

def estimate(situation):
    frame,data=copy.deepcopy(situation);return RaceStrategyService().enrich(frame,data,5.5)

def test_new_tyres_raise_the_follower_chance_and_reduce_wear(situation):
    old=estimate(situation)
    frame,data=copy.deepcopy(situation);frame['rows'][1].update(tyre_age=0,stint_start_lap=45)
    new=estimate((frame,data))
    old_p=next(r for r in old['race_forecast']['predictions'] if r['driver_number']==63)['win_probability']
    new_p=next(r for r in new['race_forecast']['predictions'] if r['driver_number']==63)['win_probability']
    assert new_p>old_p
    assert new['selected']['tyre_estimate']['wear_percent']<old['selected']['tyre_estimate']['wear_percent']

def test_wear_progresses_from_green_to_yellow_orange_red(situation):
    values=[]
    for age in (0,15,26,39):
        frame,data=copy.deepcopy(situation);frame['rows'][1]['tyre_age']=age
        values.append(estimate((frame,data))['selected']['tyre_estimate'])
    assert [v['wear_percent'] for v in values]==sorted(v['wear_percent'] for v in values)
    assert len({v['color'] for v in values})==4
    assert colour(0)=='#62dca1' and colour(100)=='#ef5b58'

def test_each_wheel_is_explicitly_the_same_set_estimate_not_fake_measurements(situation):
    est=estimate(situation)['selected']['tyre_estimate']
    assert not est['per_wheel_measured']
    assert set(est['wheels'].values())=={est['wear_percent']}

def test_missing_compound_or_age_stays_unknown(situation):
    frame,data=copy.deepcopy(situation);frame['rows'][1]['compound']=None
    assert estimate((frame,data))['selected']['tyre_estimate']['wear_percent'] is None
    frame['rows'][1]['compound']='SOFT';frame['rows'][1]['tyre_age']=None
    assert estimate((frame,data))['selected']['tyre_estimate']['wear_percent'] is None

def test_local_yellow_is_not_treated_as_safety_car_discount(situation):
    losses=[]
    for flag in ('GREEN','YELLOW','VSC','SAFETY CAR'):
        frame,data=copy.deepcopy(situation);frame['flag']=flag;forecast=estimate((frame,data))['race_forecast'];losses.append(forecast['current_pit_loss_s'])
    assert losses[0]>losses[1]>losses[2]>losses[3]
    assert losses[1]>.8*losses[0]

def test_forecast_probabilities_are_normalized_and_only_use_current_inputs(situation):
    frame=estimate(situation);f=frame['race_forecast']
    assert f['status']=='ESTIMATE' and f['experimental']
    assert sum(r['win_probability'] for r in f['predictions'])==pytest.approx(1.)
    assert f['feature_cutoff']==frame['at']
    assert '_laps_by' not in frame and '_controls' not in frame

def test_future_final_result_and_future_race_laps_do_not_change_forecast(situation):
    frame,data=copy.deepcopy(situation);before=estimate((frame,data))['race_forecast']['predictions']
    data['events']['session_result']=[{'driver_number':16,'position':1,'number_of_laps':51}]
    frame['_laps_by'][16].append({'lap':46,'complete':True,'time':2.,'date_start':date(5000),'deleted':False})
    assert estimate((frame,data))['race_forecast']['predictions']==before

def test_accident_allegation_highlights_impact_but_does_not_invent_component_damage(situation):
    frame,data=copy.deepcopy(situation);frame['_controls'].append({'date':date(700),'message':'TURN 9 INCIDENT INVOLVING CARS 3 (VER) AND 63 (RUS) NOTED - CAUSING A COLLISION'})
    f=estimate((frame,data));condition=f['selected']['condition']
    assert condition['body_alert'] and not condition['report']['damage_extent_known']
    assert set(condition['components'].values())=={'UNKNOWN'}
    assert len(f['incidents'])==2

def test_explicit_front_wing_damage_marks_only_that_component():
    c=RaceStrategyService.incident_state([{'date':date(10),'message':'CAR 63 (RUS) HAS FRONT WING DAMAGE'}],63)
    assert c['components']['front_wing']=='DAMAGE_REPORTED'
    assert c['components']['rear_wing']=='UNKNOWN' and c['components']['floor']=='UNKNOWN'

def test_false_start_investigation_is_not_damage():
    c=RaceStrategyService.incident_state([{'date':date(10),'message':'INCIDENT INVOLVING CAR 63 (RUS) NOTED - FALSE START'}],63)
    assert not c['body_alert'] and c['report'] is None

def test_confirmed_retired_driver_is_excluded_from_future_win_estimate(situation):
    frame,data=copy.deepcopy(situation);frame['_controls'].append({'date':date(700),'message':'CAR 63 (RUS) RETIRED'})
    assert not any(p['driver_number']==63 for p in estimate((frame,data))['race_forecast']['predictions'])

def test_finished_result_is_not_misrepresented_as_a_prediction(situation):
    frame,data=copy.deepcopy(situation);frame['phase']='FINISHED';frame['winner']=frame['rows'][0]
    f=estimate((frame,data))['race_forecast'];assert f['status']=='FINAL_RESULT'
    assert f['predictions'][0]['win_probability']==1.

def test_q1_q2_finishes_do_not_reveal_q3_winner_or_end_replay():
    data={'meta':{'session_type':'Qualifying','date_start':date(0),'date_end':date(900)},'complete_archive':True,'events':{'race_control':[{'date':date(0),'message':'SESSION STARTED'},{'date':date(200),'message':'SESSION FINISHED'},{'date':date(300),'message':'SESSION STARTED'},{'date':date(600),'message':'SESSION FINISHED'},{'date':date(700),'message':'SESSION STARTED'},{'date':date(900),'message':'SESSION FINISHED'}],'session_result':[{'driver_number':63,'position':1}]},'drivers':[{'driver_number':63,'code':'RUS','name':'Russell'}]}
    for at in (201,601):
        f=TimingTimeline.frame(data,stamp(date(at)),63);assert f['phase']=='BREAK' and f['winner'] is None
    assert TimingTimeline.frame(data,stamp(date(900)),63)['winner']['code']=='RUS'

def test_future_incident_message_cannot_mark_the_car_or_change_forecast(situation):
    frame,data=copy.deepcopy(situation);before=estimate((frame,data))['race_forecast']['predictions']
    frame['_controls'].append({'date':date(5000),'message':'CAR 63 (RUS) RETIRED AFTER COLLISION'})
    after=estimate((frame,data))
    assert not after['selected']['condition']['body_alert'] and not after['selected']['condition']['retired']
    assert after['race_forecast']['predictions']==before

def test_public_qualifying_phase_finish_does_not_schedule_live_connection_shutdown(monkeypatch):
    from services.race_control_service import RaceControlService
    service=RaceControlService();data={'meta':{'session_type':'Qualifying'},'public_state':{'SessionInfo':{'SessionStatus':'Started'}},'events':{},'locations':{},'telemetry':{}}
    monkeypatch.setattr(service,'datasets',{100:data});monkeypatch.setattr(service,'live',{100:{'last_message':None}})
    service.ingest_public(100,'SessionStatus',{'Status':'Finished'},date(200))
    assert 'finished_at' not in service.live[100]
    service.ingest_public(100,'SessionStatus',{'Status':'Started'},date(300))
    assert 'finished_at' not in service.live[100]
    service.ingest_public(100,'SessionInfo',{'SessionStatus':'Finalised'},date(900))
    assert service.live[100]['finished_at']==date(900)
