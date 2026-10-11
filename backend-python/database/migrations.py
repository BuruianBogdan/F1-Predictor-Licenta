"""Idempotent, additive SQLite migration. Never discard historical facts."""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import inspect, text
from database.db import Base, engine
import models.driver, models.constructor, models.circuit, models.race, models.race_result, models.analytics
import models.news, models.weekend

ADDITIONS = {
    'races': {'race_status': "VARCHAR DEFAULT 'SCHEDULED'", 'start_at': 'VARCHAR', 'weekend_at': 'VARCHAR', 'qualifying_at': 'VARCHAR', 'sprint_at': 'VARCHAR', 'results_verified': 'INTEGER DEFAULT 0', 'source': "VARCHAR DEFAULT 'legacy'"},
    'race_results': {'laps': 'INTEGER', 'race_time': 'VARCHAR', 'fastest_lap': 'VARCHAR', 'source': "VARCHAR DEFAULT 'legacy'"},
}

def _migrate_legacy():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    version = 0
    if 'schema_migrations' in tables:
        with engine.connect() as c:
            version = c.execute(text('SELECT coalesce(max(version),0) FROM schema_migrations')).scalar()
    if version >= 3:
        return {'version': version, 'changed': False}
    db = engine.url.database
    backup_path = None
    if db and db != ':memory:' and Path(db).exists() and tables:
        directory = Path(db).parent / 'backups'
        directory.mkdir(parents=True, exist_ok=True)
        backup_path = directory / f'f1-premigration-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.db'
        with sqlite3.connect(db) as src, sqlite3.connect(backup_path) as dst:
            src.backup(dst)
    if version == 2:
        Base.metadata.create_all(engine)
        with engine.begin() as c:
            c.execute(text('INSERT INTO schema_migrations VALUES(3,:now)'),{'now':datetime.now(timezone.utc).isoformat()})
        return {'version':3,'changed':True,'backup':str(backup_path) if backup_path else None}
    if version == 1:
        Base.metadata.create_all(engine)
        with engine.begin() as c:
            c.execute(text('INSERT INTO schema_migrations VALUES(2,:now)'),{'now':datetime.now(timezone.utc).isoformat()})
            c.execute(text('INSERT INTO schema_migrations VALUES(3,:now)'),{'now':datetime.now(timezone.utc).isoformat()})
        return {'version':3,'changed':True,'backup':str(backup_path) if backup_path else None}
    with engine.begin() as c:
        for table, additions in ADDITIONS.items():
            if table not in tables:
                continue
            columns = {col['name'] for col in inspector.get_columns(table)}
            for name, sql_type in additions.items():
                if name not in columns:
                    c.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {sql_type}'))
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        # Fail loudly if ambiguous duplicates need manual reconciliation.
        c.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_race_season_round ON races(season_year, round)'))
        c.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_result_race_driver ON race_results(race_id, driver_id)'))
        c.execute(text('CREATE INDEX IF NOT EXISTS ix_result_driver ON race_results(driver_id)'))
        c.execute(text('CREATE INDEX IF NOT EXISTS ix_race_date ON races(date)'))
        # Legacy imports were truncated; only a fresh complete provider payload verifies results.
        c.execute(text("UPDATE races SET is_completed=0, race_status='SCHEDULED', results_verified=0"))
        # Retrofit FK protection without rebuilding the old table or changing any IDs.
        for field, parent in [('race_id','races'),('driver_id','drivers'),('constructor_id','constructors')]:
            for action in ['INSERT','UPDATE']:
                c.execute(text(f"CREATE TRIGGER IF NOT EXISTS fk_results_{field}_{action.lower()} BEFORE {action} ON race_results WHEN NEW.{field} IS NULL OR NOT EXISTS (SELECT 1 FROM {parent} WHERE {field}=NEW.{field}) BEGIN SELECT RAISE(ABORT, 'Invalid result reference'); END"))
            c.execute(text(f"CREATE TRIGGER IF NOT EXISTS protect_{parent}_delete BEFORE DELETE ON {parent} WHEN EXISTS(SELECT 1 FROM race_results WHERE {field}=OLD.{field}) BEGIN SELECT RAISE(ABORT, 'Entity has race results'); END"))
        c.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)'))
        c.execute(text("INSERT INTO schema_migrations VALUES(1, :now)"), {'now':datetime.now(timezone.utc).isoformat()})
        c.execute(text("INSERT INTO schema_migrations VALUES(2, :now)"), {'now':datetime.now(timezone.utc).isoformat()})
        c.execute(text("INSERT INTO schema_migrations VALUES(3, :now)"), {'now':datetime.now(timezone.utc).isoformat()})
    return {'version':3, 'changed':True, 'backup':str(backup_path) if backup_path else None}

def migrate():
    return _migrate_legacy()
