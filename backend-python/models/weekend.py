"""Versioned observations: a later refresh never rewrites an older forecast's inputs."""
from sqlalchemy import Column,Integer,String,ForeignKey,JSON,Index
from database.db import Base

class WeekendSessionSnapshot(Base):
    __tablename__='weekend_session_snapshots'
    id=Column(Integer,primary_key=True)
    race_id=Column(Integer,ForeignKey('races.race_id'),nullable=False)
    session=Column(String,nullable=False)
    source_url=Column(String,nullable=False)
    source=Column(String,nullable=False)
    session_start_at=Column(String,nullable=False)
    session_end_at=Column(String,nullable=False)
    observed_at=Column(String,nullable=False)
    content_hash=Column(String,nullable=False)
    data=Column(JSON,nullable=False)
    __table_args__=(Index('ix_weekend_race_observed','race_id','observed_at'),)

class WeekendState(Base):
    __tablename__='weekend_states'
    race_id=Column(Integer,ForeignKey('races.race_id'),primary_key=True)
    schedule=Column(JSON)
    last_checked_at=Column(String)
    last_success_at=Column(String)
    status=Column(String)
    details=Column(JSON)
    forecasts=Column(JSON)
