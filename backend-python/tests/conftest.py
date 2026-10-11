import os,sys,tempfile
from pathlib import Path
TEST_ROOT=Path(tempfile.mkdtemp(prefix='f1-predictor-tests-'))
os.environ['DATABASE_URL']='sqlite:///'+str(TEST_ROOT/'test.db')
os.environ['F1_DATA_DIR']=str(TEST_ROOT/'data')
os.environ['LLM_ENABLED']='false'
os.environ['SELENIUM_ENABLED']='false'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from database.db import Base,engine,SessionLocal
import models.driver,models.constructor,models.circuit,models.race,models.race_result,models.analytics

@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    yield

@pytest.fixture
def race_field():
    from datetime import date,timedelta
    from models.driver import Driver
    from models.constructor import Constructor
    from models.circuit import Circuit
    from models.race import Race
    from models.race_result import RaceResult
    from models.analytics import RaceEntry,QualifyingResult
    with SessionLocal.begin() as s:
        s.add(Circuit(circuit_id=1,circuit_ref='test',name='Test circuit'))
        for team in range(1,7):s.add(Constructor(constructor_id=team,constructor_ref=f'team{team}',name=f'Team {team}'))
        for driver in range(1,13):s.add(Driver(driver_id=driver,driver_ref=f'driver{driver}',forename='Pilot',surname=str(driver),code=f'D{driver}'))
        s.flush()
        for round_number,race_id in enumerate([90,4,72,2,55],1):
            day=date(2025,3,1)+timedelta(days=14*round_number)
            race=Race(race_id=race_id,season_year=2025,round=round_number,circuit_id=1,race_name=f'Race {round_number}',date=day,start_at=f'{day}T14:00:00+00:00',weekend_at=f'{day-timedelta(days=2)}T10:00:00+00:00',qualifying_at=f'{day-timedelta(days=1)}T14:00:00+00:00',is_completed=1,results_verified=1,race_status='COMPLETED',source='jolpica');s.add(race);s.flush()
            for driver in range(1,13):
                s.add(RaceEntry(race_id=race_id,driver_id=driver,constructor_id=(driver+1)//2,source='jolpica'))
                s.add(RaceResult(race_id=race_id,driver_id=driver,constructor_id=(driver+1)//2,position=driver,grid=13-driver,points=max(0,26-driver*2),status='Finished',source='jolpica'))
                s.add(QualifyingResult(race_id=race_id,driver_id=driver,position=driver,available_at=f'{day-timedelta(days=1)}T17:00:00+00:00',source='jolpica'))
    return {'target':72,'previous':4,'future':2}
