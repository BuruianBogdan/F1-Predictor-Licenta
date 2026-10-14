# Architecture

## Boundaries and dependency map

| Spring controller | API service / Flask endpoint | Python service | Persistence |
|---|---|---|---|
| DashboardController | FlaskApiService → /dashboard/overview | DashboardService, SeasonContext, InsightService, PredictionService | races, results, standings, local model |
| CrudController | FlaskApiService → /drivers, /constructors, /circuits, /races, /results | Original entity services → typed repositories | Five original SQLAlchemy models |
| PredictionController | /predict/race/:id, /market | FeatureEngineeringService → RaceMLModel or HeuristicBaselineModel → OddsService → HistoryService | race_entries, qualifying, results, prediction_runs, odds_snapshots |
| IntelligenceController | /races/:id/detail, /drivers/:id/detail | InsightService, MediaService | confirmed results, driver_media, session_data |
| IntelligenceController | /predict/championship | ChampionshipSimulationService | current standings, remaining calendar, prediction_runs |
| IntelligenceController | /data/*, /model/* | F1DataSyncService, JobService, training | data_sync_runs, model_metrics, joblib artifacts |
| SimulatorController / RegulationController | /scenarios, /regulations | ScenarioService, RegulationService, PredictionService | local JSON settings and prediction_runs |
| HistoryController / ExportController | /prediction-history, /export/* | HistoryService, ExportService | persisted forecasts, evaluations and CSV |

The project preserves `com.f1predictor.frontendjava`; no duplicate package tree was introduced. Flask blueprints preserve old public paths. Legacy prediction DTO/API-service and Elo/standings repository files remain for compatibility but are not the active prediction pipeline. The authoritative path is the one above.

## Database

Original tables remain: drivers, constructors, circuits, races, race_results. Additive columns track session timestamps, verification/source/status, laps, duration and fastest lap. New tables have actual consumers: race_entries, qualifying_results, sprint_results, standing_snapshots, data_sync_runs, prediction_runs, odds_snapshots, driver_media, session_data, model_metrics, explanation_cache and schema_migrations.

Identity is separate from participation: `(race_id, driver_id)` identifies a race entry with that race's constructor. A driver changing teams does not rewrite previous results. Prediction entries and metadata are stored as JSON within an immutable run; an extra relational entry table is unnecessary for the current read patterns.

SQLite has foreign-key checks enabled, unique race-season/round and race/driver result constraints, reference checks and protective triggers for legacy results. `database/schema.sql` under the backend is a validated reference snapshot. Use `scripts/migrate_database.py`, not manually applying the snapshot, to upgrade existing data.

## Runtime

Dashboard reads the local database and performs one small, non-persisted model preview. It never synchronizes, trains, launches Selenium, calls an LLM or runs championship simulation. Inference artifacts are cached by path/mtime. Training, synchronization, market refresh and explanations are explicit operations.

A one-worker in-process executor handles UI synchronization/training jobs. Job status disappears on restart; synchronization facts and status are durable in SQLite. This is suitable for a local thesis application, not distributed job orchestration.

Spring handles backend errors with a friendly page and never exposes browser stack traces. Flask emits structured errors plus the old message field. Request bodies are limited to 1 MiB. Administrative operations require a configured bearer token, or loopback when no token is set. CRUD routes retain the original local-use model; do not expose this deployment directly to the internet.
# Race Control source integration

The existing timing room now composes a single public SignalR transport, an observation/provenance ledger and bounded live checkpoints with separate OpenF1/FastF1 replay datasets. Published result records supply a read-only provisional championship baseline; they are never overwritten by live projections. Diagnostics and projections remain inside the original viewer and API namespace. See [LIVE_DATA_ARCHITECTURE.md](LIVE_DATA_ARCHITECTURE.md) and [LIVE_DATA_SCHEMA.md](LIVE_DATA_SCHEMA.md). No removed data-platform or OCR module is restored.

## Live Data v2 completion
Race Control reuses its existing Flask service, shared public feed and FlaskApiService proxy. See [completion audit](LIVE_COMPLETION_AUDIT.md) for changes and [result contract](LIVE_DATA_SCHEMA.md) for publication-cutoff versus latest historical outcome semantics. Existing versioned weekend storage is reused for GP corrections; the SQL schema remains unchanged.
