from datetime import timedelta
from pathlib import Path
import json
import pytest
from database.db import SessionLocal
from models.race import Race
from models.weekend import WeekendState,WeekendSessionSnapshot
from models.analytics import SprintResult,StandingSnapshot
from services.weekend_service import WeekendService
from services.live_prediction_service import LivePredictionService,SprintUnavailableError,EventStartedError
from services.season_service import utcnow,iso
from services.standings_service import StandingsService
from data_sources.weekend_provider import parse_schedule,parse_classification

@pytest.fixture
def weekend(race_field):
    now=utcnow();day=(now+timedelta(days=3)).date()
    with SessionLocal.begin() as s:
        s.add(Race(race_id=999,season_year=2025,round=6,circuit_id=1,race_name='Test Grand Prix',date=day,start_at=iso(now+timedelta(days=3)),weekend_at=iso(now-timedelta(hours=6)),sprint_at=iso(now+timedelta(days=1)),qualifying_at=iso(now+timedelta(days=2)),is_completed=0,results_verified=0,race_status='SCHEDULED'))
    return now

def rows(leader=1,points=False):
    order=[leader]+[d for d in range(1,13) if d!=leader]
    return [{'driver_id':d,'driver_code':f'D{d}','constructor_id':(d+1)//2,'driver_name':f'Pilot {d}','constructor_name':f'Team {(d+1)//2}','position':rank,'best_lap_seconds':92+(rank-1)*.3,'time_text':f'1:{32+(rank-1)*.3:06.3f}','laps':20,'status':'classified','points':max(0,9-rank) if points else None} for rank,d in enumerate(order,1)]

def observe(code,now,leader=1,observed=None):
    with SessionLocal.begin() as s:
        row=WeekendSessionSnapshot(race_id=999,session=code,source='fixture',source_url='https://www.formula1.com/en/results/test',session_start_at=iso(now-timedelta(hours=4)),session_end_at=iso(now-timedelta(hours=3)),observed_at=iso(observed or now-timedelta(hours=2)),content_hash=str(leader),data=rows(leader));s.add(row);s.flush();return row.id

def probabilities(result):return {p['driver_id']:p['win_probability'] for p in result['predictions']}

def test_later_practice_leader_changes_forecast_and_keeps_both_sessions(weekend):
    observe('FP1',weekend,1)
    before=LivePredictionService().predict(999,persist=False)
    observe('FP2',weekend,2)
    after=LivePredictionService().predict(999,persist=False)
    assert probabilities(after)[2]>probabilities(before)[2]
    assert len(after['session_snapshot_ids'])==2
    assert sum(probabilities(after).values())==pytest.approx(1)
    assert all(0<=p['win_probability']<=p['podium_probability']<=p['points_probability']<=1 for p in after['predictions'])

def test_sprint_qualifying_has_target_specific_effect_and_gp_q_is_excluded(weekend):
    observe('FP1',weekend,1);observe('SQ',weekend,2);q_id=observe('Q',weekend,3)
    sprint=LivePredictionService().predict(999,'SPRINT',persist=False)
    gp=LivePredictionService().predict(999,'RACE',persist=False)
    assert q_id not in sprint['session_snapshot_ids'] and q_id in gp['session_snapshot_ids']
    assert probabilities(sprint)!=probabilities(gp)
    assert sprint['points_places']==8 and gp['points_places']==10
    assert sum(p['expected_points'] for p in sprint['predictions'])<=36.1

def test_observation_collected_after_cutoff_cannot_change_old_prediction(weekend):
    observe('FP1',weekend,1,weekend-timedelta(hours=2))
    as_of=weekend-timedelta(hours=1)
    before=LivePredictionService().predict(999,persist=False,as_of=as_of)
    observe('FP1',weekend,2,weekend-timedelta(minutes=10))
    after=LivePredictionService().predict(999,persist=False,as_of=as_of)
    assert probabilities(before)==probabilities(after)
    assert len(after['session_snapshot_ids'])==1

def test_grid_supersedes_qualifying_instead_of_counting_same_grid_twice(weekend):
    q=observe('Q',weekend,1);grid=observe('RACE_GRID',weekend,3)
    prediction=LivePredictionService().predict(999,persist=False)
    assert grid in prediction['session_snapshot_ids'] and q not in prediction['session_snapshot_ids']
    assert not prediction['news_factor_used']

def test_sprint_is_not_available_on_normal_weekend_and_started_event_is_locked(weekend):
    with SessionLocal.begin() as s:s.get(Race,999).sprint_at=None
    with pytest.raises(SprintUnavailableError):LivePredictionService().predict(999,'SPRINT')
    with SessionLocal.begin() as s:s.get(Race,999).sprint_at=iso(weekend-timedelta(hours=1))
    with pytest.raises(EventStartedError):LivePredictionService().predict(999,'SPRINT')

class FixtureProvider:
    def __init__(self,now,sprint=False):self.now=now;self.sprint=sprint
    def fetch(self,*args):
        code='SPRINT' if self.sprint else 'FP1';now=self.now
        schedule={'sessions':[{'code':'FP1','name':'Practice 1','start_at':iso(now-timedelta(hours=4)),'end_at':iso(now-timedelta(hours=3))},{'code':'SPRINT','name':'Sprint','start_at':iso(now-timedelta(hours=4) if self.sprint else now+timedelta(days=1)),'end_at':iso(now-timedelta(hours=3) if self.sprint else now+timedelta(days=1,hours=1))},{'code':'R','name':'Race','start_at':iso(now+timedelta(days=3)),'end_at':iso(now+timedelta(days=3,hours=2))}]}
        return {'schedule':schedule,'sessions':[{'code':code,'start_at':iso(now-timedelta(hours=4)),'end_at':iso(now-timedelta(hours=3)),'source_url':'https://www.formula1.com/en/results/test','source':'fixture','rows':rows(points=self.sprint)}],'waiting':[],'errors':[]}

def test_refresh_is_idempotent_and_preserves_observation_time(weekend):
    service=WeekendService();service.refresh(999,FixtureProvider(weekend),calculate=False)
    before=service.observations(999,utcnow())
    with SessionLocal.begin() as s:s.get(WeekendState,999).last_checked_at=iso(weekend-timedelta(minutes=2))
    second=service.refresh(999,FixtureProvider(weekend),calculate=False)
    assert second['details']['unchanged_sessions']==['FP1']
    assert service.observations(999,utcnow())==before

def test_provider_failure_retains_saved_classification_and_last_success(weekend):
    service=WeekendService();service.refresh(999,FixtureProvider(weekend),calculate=False)
    with SessionLocal.begin() as s:s.get(WeekendState,999).last_checked_at=iso(weekend-timedelta(minutes=2))
    previous=service.status(999)['last_success_at']
    class Offline:
        def fetch(self,*args):raise RuntimeError('Source offline')
    with pytest.raises(RuntimeError):service.refresh(999,Offline(),calculate=False)
    status=service.status(999)
    assert status['status']=='FAILED' and status['last_success_at']==previous
    assert status['sessions'][0]['leader']['driver_id']==1

def test_pre_weekend_sprint_excludes_all_current_session_observations(weekend):
    observe('FP1',weekend,2);observe('SQ',weekend,3)
    result=LivePredictionService().predict(999,'SPRINT',persist=False,pre_weekend=True)
    assert not result['session_factor_used'] and not result['session_snapshot_ids']

FIXTURES=Path(__file__).parent/'fixtures'
def test_official_parser_reconstructs_fp_gap_and_separates_sq_from_grid():
    html=(FIXTURES/'weekend-fp1.html').read_text();parsed=parse_classification(html,'FP1')
    assert parsed[0]['driver_code']=='RUS' and parsed[0]['best_lap_seconds']==pytest.approx(92.274)
    assert parsed[1]['best_lap_seconds']==pytest.approx(92.472)
    sq=(FIXTURES/'weekend-sq.html').read_text()
    assert parse_classification(sq,'SQ')[0]['driver_code']=='VER'
    assert parse_classification(sq,'SPRINT_GRID')==[]

def test_sprint_weekend_schedule_does_not_invent_fp2_or_fp3():
    schedule=parse_schedule((FIXTURES/'weekend-schedule.html').read_text())
    assert [x['code'] for x in schedule['sessions']]==['FP1','SQ','SPRINT','Q','R']

def test_sprint_result_changes_gp_estimate_without_simulating_earned_sprint_points_again(weekend):
    from services.championship_service import ChampionshipSimulationService
    observe('FP1',weekend,1)
    before=LivePredictionService().predict(999,persist=False)
    WeekendService().refresh(999,FixtureProvider(weekend,True),calculate=False)
    after=LivePredictionService().predict(999,persist=False)
    assert 'SPRINT' in {c['session'] for c in after['session_components']}
    assert probabilities(after)!=probabilities(before)
    champion=ChampionshipSimulationService().simulate(2025,100,42)
    assert champion['remaining_sprints']==0
    assert 999 in champion['weekend_adjusted_races']

def test_sprint_reliability_prior_reflects_shorter_distance(weekend):
    observe('SQ',weekend,2)
    sprint=LivePredictionService().predict(999,'SPRINT',persist=False)
    assert all(p['reliability_rate']>=p['baseline_reliability_rate'] for p in sprint['predictions'])

def test_official_event_matches_british_name_to_great_britain_slug(weekend,monkeypatch):
    from types import SimpleNamespace
    from data_sources.weekend_provider import OfficialWeekendProvider
    provider=OfficialWeekendProvider();start=weekend+timedelta(days=3)
    schedule={'@type':'SportsEvent','name':'British Grand Prix','subEvent':[{'name':'Race - British Grand Prix','startDate':iso(start),'endDate':iso(start+timedelta(hours=2))}]}
    def html(url):return '<a href="/en/results/2025/races/123/great-britain/race-result">Great Britain</a>' if '/results/' in url else '<script type="application/ld+json">'+json.dumps(schedule)+'</script>'
    monkeypatch.setattr(provider,'get',html)
    race=SimpleNamespace(season_year=2025,race_name='British Grand Prix',date=start.date())
    result=provider.resolve(race,SimpleNamespace(country='UK',circuit_ref='silverstone'))
    assert result['results_base'].endswith('/great-britain')
    race.date=(start+timedelta(days=1)).date()
    from data_sources.base_provider import ProviderError
    with pytest.raises(ProviderError,match='date differs'):provider.resolve(race,SimpleNamespace(country='UK',circuit_ref='silverstone'))
