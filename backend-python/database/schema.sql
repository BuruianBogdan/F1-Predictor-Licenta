-- Reference schema only. Initialize or upgrade with scripts/migrate_database.py.
-- Existing database IDs and data are preserved by the additive migration.
PRAGMA foreign_keys=ON;

CREATE TABLE circuits (
	circuit_id INTEGER NOT NULL, 
	circuit_ref VARCHAR, 
	name VARCHAR, 
	location VARCHAR, 
	country VARCHAR, 
	lat FLOAT, 
	lng FLOAT, 
	PRIMARY KEY (circuit_id), 
	UNIQUE (circuit_ref)
);

CREATE TABLE constructors (
	constructor_id INTEGER NOT NULL, 
	constructor_ref VARCHAR, 
	name VARCHAR, 
	nationality VARCHAR, 
	PRIMARY KEY (constructor_id), 
	UNIQUE (constructor_ref)
);

CREATE TABLE data_sync_runs (
	id INTEGER NOT NULL, 
	season INTEGER NOT NULL, 
	started_at VARCHAR NOT NULL, 
	completed_at VARCHAR, 
	status VARCHAR NOT NULL, 
	summary JSON, 
	PRIMARY KEY (id)
);

CREATE TABLE driver_media (
	driver_id INTEGER NOT NULL, 
	image_url VARCHAR, 
	team_color VARCHAR, 
	source VARCHAR, 
	updated_at VARCHAR, 
	PRIMARY KEY (driver_id), 
	FOREIGN KEY(driver_id) REFERENCES drivers (driver_id)
);

CREATE TABLE drivers (
	driver_id INTEGER NOT NULL, 
	driver_ref VARCHAR, 
	number INTEGER, 
	code VARCHAR, 
	forename VARCHAR, 
	surname VARCHAR, 
	dob DATE, 
	nationality VARCHAR, 
	PRIMARY KEY (driver_id), 
	UNIQUE (driver_ref)
);

CREATE TABLE explanation_cache (
	"key" VARCHAR NOT NULL, 
	data JSON NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY ("key")
);

CREATE TABLE model_metrics (
	id INTEGER NOT NULL, 
	model_version VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	data JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE odds_snapshots (
	id INTEGER NOT NULL, 
	race_id INTEGER NOT NULL, 
	provider VARCHAR NOT NULL, 
	captured_at VARCHAR NOT NULL, 
	source_url VARCHAR, 
	data JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(race_id) REFERENCES races (race_id)
);

CREATE TABLE prediction_runs (
	id VARCHAR NOT NULL, 
	kind VARCHAR NOT NULL, 
	race_id INTEGER, 
	created_at VARCHAR NOT NULL, 
	model_version VARCHAR, 
	training_cutoff VARCHAR, 
	feature_cutoff VARCHAR, 
	feature_mode VARCHAR, 
	market_enabled INTEGER, 
	odds_snapshot_id INTEGER, 
	replay INTEGER, 
	predictions JSON NOT NULL, 
	meta JSON, 
	accuracy JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(race_id) REFERENCES races (race_id), 
	FOREIGN KEY(odds_snapshot_id) REFERENCES odds_snapshots (id)
);

CREATE TABLE qualifying_results (
	id INTEGER NOT NULL, 
	race_id INTEGER NOT NULL, 
	driver_id INTEGER NOT NULL, 
	position INTEGER, 
	q1 VARCHAR, 
	q2 VARCHAR, 
	q3 VARCHAR, 
	available_at VARCHAR NOT NULL, 
	source VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (race_id, driver_id), 
	FOREIGN KEY(race_id) REFERENCES races (race_id), 
	FOREIGN KEY(driver_id) REFERENCES drivers (driver_id)
);

CREATE TABLE race_entries (
	entry_id INTEGER NOT NULL, 
	race_id INTEGER NOT NULL, 
	driver_id INTEGER NOT NULL, 
	constructor_id INTEGER NOT NULL, 
	source VARCHAR NOT NULL, 
	PRIMARY KEY (entry_id), 
	UNIQUE (race_id, driver_id), 
	FOREIGN KEY(race_id) REFERENCES races (race_id), 
	FOREIGN KEY(driver_id) REFERENCES drivers (driver_id), 
	FOREIGN KEY(constructor_id) REFERENCES constructors (constructor_id)
);

CREATE TABLE race_results (
	result_id INTEGER NOT NULL, 
	race_id INTEGER, 
	driver_id INTEGER, 
	constructor_id INTEGER, 
	grid INTEGER, 
	position INTEGER, 
	points FLOAT, 
	status VARCHAR, laps INTEGER, race_time VARCHAR, fastest_lap VARCHAR, source VARCHAR DEFAULT 'legacy', 
	PRIMARY KEY (result_id)
);

CREATE TABLE races (
	race_id INTEGER NOT NULL, 
	season_year INTEGER NOT NULL, 
	round INTEGER NOT NULL, 
	circuit_id INTEGER, 
	race_name VARCHAR, 
	date DATE, 
	is_completed INTEGER, race_status VARCHAR DEFAULT 'SCHEDULED', start_at VARCHAR, weekend_at VARCHAR, qualifying_at VARCHAR, sprint_at VARCHAR, results_verified INTEGER DEFAULT 0, source VARCHAR DEFAULT 'legacy', 
	PRIMARY KEY (race_id), 
	FOREIGN KEY(circuit_id) REFERENCES circuits (circuit_id)
);

CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

CREATE TABLE session_data (
	id INTEGER NOT NULL, 
	race_id INTEGER NOT NULL, 
	session VARCHAR NOT NULL, 
	data JSON NOT NULL, 
	source VARCHAR NOT NULL, 
	updated_at VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (race_id, session), 
	FOREIGN KEY(race_id) REFERENCES races (race_id)
);

CREATE TABLE sprint_results (
	id INTEGER NOT NULL, 
	race_id INTEGER NOT NULL, 
	driver_id INTEGER NOT NULL, 
	constructor_id INTEGER NOT NULL, 
	position INTEGER, 
	points FLOAT, 
	available_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (race_id, driver_id), 
	FOREIGN KEY(race_id) REFERENCES races (race_id), 
	FOREIGN KEY(driver_id) REFERENCES drivers (driver_id), 
	FOREIGN KEY(constructor_id) REFERENCES constructors (constructor_id)
);

CREATE TABLE standing_snapshots (
	id INTEGER NOT NULL, 
	season INTEGER NOT NULL, 
	kind VARCHAR NOT NULL, 
	round INTEGER NOT NULL, 
	data JSON NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (season, kind)
);

CREATE INDEX ix_race_date ON races(date);

CREATE INDEX ix_result_driver ON race_results(driver_id);

CREATE UNIQUE INDEX uq_race_season_round ON races(season_year, round);

CREATE UNIQUE INDEX uq_result_race_driver ON race_results(race_id, driver_id);

CREATE TRIGGER fk_results_constructor_id_insert BEFORE INSERT ON race_results WHEN NEW.constructor_id IS NULL OR NOT EXISTS (SELECT 1 FROM constructors WHERE constructor_id=NEW.constructor_id) BEGIN SELECT RAISE(ABORT, 'Invalid result reference'); END;

CREATE TRIGGER fk_results_constructor_id_update BEFORE UPDATE ON race_results WHEN NEW.constructor_id IS NULL OR NOT EXISTS (SELECT 1 FROM constructors WHERE constructor_id=NEW.constructor_id) BEGIN SELECT RAISE(ABORT, 'Invalid result reference'); END;

CREATE TRIGGER fk_results_driver_id_insert BEFORE INSERT ON race_results WHEN NEW.driver_id IS NULL OR NOT EXISTS (SELECT 1 FROM drivers WHERE driver_id=NEW.driver_id) BEGIN SELECT RAISE(ABORT, 'Invalid result reference'); END;

CREATE TRIGGER fk_results_driver_id_update BEFORE UPDATE ON race_results WHEN NEW.driver_id IS NULL OR NOT EXISTS (SELECT 1 FROM drivers WHERE driver_id=NEW.driver_id) BEGIN SELECT RAISE(ABORT, 'Invalid result reference'); END;

CREATE TRIGGER fk_results_race_id_insert BEFORE INSERT ON race_results WHEN NEW.race_id IS NULL OR NOT EXISTS (SELECT 1 FROM races WHERE race_id=NEW.race_id) BEGIN SELECT RAISE(ABORT, 'Invalid result reference'); END;

CREATE TRIGGER fk_results_race_id_update BEFORE UPDATE ON race_results WHEN NEW.race_id IS NULL OR NOT EXISTS (SELECT 1 FROM races WHERE race_id=NEW.race_id) BEGIN SELECT RAISE(ABORT, 'Invalid result reference'); END;

CREATE TRIGGER protect_constructors_delete BEFORE DELETE ON constructors WHEN EXISTS(SELECT 1 FROM race_results WHERE constructor_id=OLD.constructor_id) BEGIN SELECT RAISE(ABORT, 'Entity has race results'); END;

CREATE TRIGGER protect_drivers_delete BEFORE DELETE ON drivers WHEN EXISTS(SELECT 1 FROM race_results WHERE driver_id=OLD.driver_id) BEGIN SELECT RAISE(ABORT, 'Entity has race results'); END;

CREATE TRIGGER protect_races_delete BEFORE DELETE ON races WHEN EXISTS(SELECT 1 FROM race_results WHERE race_id=OLD.race_id) BEGIN SELECT RAISE(ABORT, 'Entity has race results'); END;

CREATE TABLE news_articles (
	id INTEGER NOT NULL, 
	source_url VARCHAR NOT NULL, 
	source_title VARCHAR NOT NULL, 
	title VARCHAR NOT NULL, 
	summary VARCHAR NOT NULL, 
	source_excerpt VARCHAR NOT NULL, 
	image_url VARCHAR, 
	published_at VARCHAR, 
	observed_at VARCHAR NOT NULL, 
	source_hash VARCHAR NOT NULL, 
	summary_status VARCHAR NOT NULL, 
	summary_model VARCHAR, 
	language VARCHAR, 
	source VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (source_url)
);

CREATE TABLE news_signals (
	id INTEGER NOT NULL, 
	article_id INTEGER NOT NULL, 
	race_id INTEGER NOT NULL, 
	driver_id INTEGER, 
	constructor_id INTEGER, 
	kind VARCHAR NOT NULL, 
	log_weight FLOAT NOT NULL, 
	evidence VARCHAR NOT NULL, 
	observed_at VARCHAR NOT NULL, 
	published_at VARCHAR NOT NULL, 
	expires_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(article_id) REFERENCES news_articles (id), 
	FOREIGN KEY(race_id) REFERENCES races (race_id), 
	FOREIGN KEY(driver_id) REFERENCES drivers (driver_id), 
	FOREIGN KEY(constructor_id) REFERENCES constructors (constructor_id)
);

CREATE TABLE news_crawl_runs (
	id INTEGER NOT NULL, 
	started_at VARCHAR NOT NULL, 
	completed_at VARCHAR, 
	status VARCHAR NOT NULL, 
	data JSON, 
	PRIMARY KEY (id)
);

CREATE TABLE news_automation (
	id INTEGER NOT NULL, 
	enabled INTEGER NOT NULL, 
	interval_minutes INTEGER NOT NULL, 
	next_run_at VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE weekend_session_snapshots (
	id INTEGER NOT NULL, 
	race_id INTEGER NOT NULL, 
	session VARCHAR NOT NULL, 
	source_url VARCHAR NOT NULL, 
	source VARCHAR NOT NULL, 
	session_start_at VARCHAR NOT NULL, 
	session_end_at VARCHAR NOT NULL, 
	observed_at VARCHAR NOT NULL, 
	content_hash VARCHAR NOT NULL, 
	data JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(race_id) REFERENCES races (race_id)
);

CREATE INDEX ix_weekend_race_observed ON weekend_session_snapshots (race_id, observed_at);

CREATE TABLE weekend_states (
	race_id INTEGER NOT NULL, 
	schedule JSON, 
	last_checked_at VARCHAR, 
	last_success_at VARCHAR, 
	status VARCHAR, 
	details JSON, 
	forecasts JSON, 
	PRIMARY KEY (race_id), 
	FOREIGN KEY(race_id) REFERENCES races (race_id)
);
