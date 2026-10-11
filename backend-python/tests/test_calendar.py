from datetime import date,timedelta
from database.db import SessionLocal
from models.race import Race
from services.circuit_service import CircuitPresentationService,layouts
from services.season_service import utcnow

def test_future_races_chronological_and_archive_newest_first(race_field):
    now=utcnow()
    with SessionLocal.begin() as s:
        for rid,days in [(800,14),(600,7)]:
            day=now.date()+timedelta(days=days)
            s.add(Race(race_id=rid,season_year=now.year,round=rid,date=day,race_name='Future race',circuit_id=1,is_completed=0,results_verified=0,race_status='SCHEDULED'))
    result=CircuitPresentationService().calendar(now.year)
    assert [r['race_id'] for r in result['upcoming']]==[600,800]
    assert result['next']['race_id']==600
    archive=CircuitPresentationService().calendar(2025)['completed']
    assert [r['date'] for r in archive]==sorted([r['date'] for r in archive],reverse=True)

def test_circuit_geometry_available_and_unknown_is_honest():
    assert len(layouts())>=24 and layouts()['monaco']['path'].startswith('M')
    assert not CircuitPresentationService().present(None)['layout_available']
