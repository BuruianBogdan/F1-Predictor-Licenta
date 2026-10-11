"""Entities with a concrete synchronization, inference or audit consumer."""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint, JSON
from database.db import Base

class RaceEntry(Base):
    __tablename__ = 'race_entries'
    entry_id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey('races.race_id'), nullable=False)
    driver_id = Column(Integer, ForeignKey('drivers.driver_id'), nullable=False)
    constructor_id = Column(Integer, ForeignKey('constructors.constructor_id'), nullable=False)
    source = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint('race_id', 'driver_id'),)

class QualifyingResult(Base):
    __tablename__ = 'qualifying_results'
    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey('races.race_id'), nullable=False)
    driver_id = Column(Integer, ForeignKey('drivers.driver_id'), nullable=False)
    position = Column(Integer)
    q1 = Column(String)
    q2 = Column(String)
    q3 = Column(String)
    available_at = Column(String, nullable=False)
    source = Column(String, default='jolpica')
    __table_args__ = (UniqueConstraint('race_id', 'driver_id'),)

class SprintResult(Base):
    __tablename__ = 'sprint_results'
    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey('races.race_id'), nullable=False)
    driver_id = Column(Integer, ForeignKey('drivers.driver_id'), nullable=False)
    constructor_id = Column(Integer, ForeignKey('constructors.constructor_id'), nullable=False)
    position = Column(Integer)
    points = Column(Float, default=0)
    available_at = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint('race_id', 'driver_id'),)

class StandingSnapshot(Base):
    __tablename__ = 'standing_snapshots'
    id = Column(Integer, primary_key=True)
    season = Column(Integer, nullable=False)
    kind = Column(String, nullable=False)
    round = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    updated_at = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint('season', 'kind'),)

class DataSyncRun(Base):
    __tablename__ = 'data_sync_runs'
    id = Column(Integer, primary_key=True)
    season = Column(Integer, nullable=False)
    started_at = Column(String, nullable=False)
    completed_at = Column(String)
    status = Column(String, nullable=False)
    summary = Column(JSON)

class PredictionRun(Base):
    __tablename__ = 'prediction_runs'
    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False)
    race_id = Column(Integer, ForeignKey('races.race_id'))
    created_at = Column(String, nullable=False)
    model_version = Column(String)
    training_cutoff = Column(String)
    feature_cutoff = Column(String)
    feature_mode = Column(String)
    market_enabled = Column(Integer, default=0)
    odds_snapshot_id = Column(Integer, ForeignKey('odds_snapshots.id'))
    replay = Column(Integer, default=0)
    predictions = Column(JSON, nullable=False)
    meta = Column(JSON)
    accuracy = Column(JSON)

class OddsSnapshot(Base):
    __tablename__ = 'odds_snapshots'
    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey('races.race_id'), nullable=False)
    provider = Column(String, nullable=False)
    captured_at = Column(String, nullable=False)
    source_url = Column(String)
    data = Column(JSON, nullable=False)

class DriverMedia(Base):
    __tablename__ = 'driver_media'
    driver_id = Column(Integer, ForeignKey('drivers.driver_id'), primary_key=True)
    image_url = Column(String)
    team_color = Column(String)
    source = Column(String)
    updated_at = Column(String)

class SessionData(Base):
    __tablename__ = 'session_data'
    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey('races.race_id'), nullable=False)
    session = Column(String, nullable=False)
    data = Column(JSON, nullable=False)
    source = Column(String, nullable=False)
    updated_at = Column(String)
    __table_args__ = (UniqueConstraint('race_id', 'session'),)

class ModelMetrics(Base):
    __tablename__ = 'model_metrics'
    id = Column(Integer, primary_key=True)
    model_version = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    data = Column(JSON, nullable=False)

class ExplanationCache(Base):
    __tablename__ = 'explanation_cache'
    key = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)
    created_at = Column(String, nullable=False)
