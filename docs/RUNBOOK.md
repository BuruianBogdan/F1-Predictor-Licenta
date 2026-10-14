# Runbook

All Python commands below run from the repository root with `backend-python/.venv/bin/python`; no global Python package installation is required.

## Installation and startup

```sh
python3 -m venv backend-python/.venv
backend-python/.venv/bin/python -m pip install -r backend-python/requirements-dev.txt
backend-python/.venv/bin/python -m pip install -r backend-python/requirements-llm.txt
```

The second requirements file is optional. Copy `.env.example` only if no local `.env` exists. The core application needs neither Chrome, FastF1 nor OpenAI. Java 17+ and Maven are required for the frontend. Local verification used Java 21.

```sh
backend-python/.venv/bin/python scripts/backup_database.py
backend-python/.venv/bin/python scripts/migrate_database.py
backend-python/.venv/bin/python backend-python/app.py
```

In a second terminal:

```sh
cd frontend-java/frontend-java
mvn spring-boot:run
```

For a packaged frontend:

```sh
mvn -f frontend-java/frontend-java/pom.xml test package
java -jar frontend-java/frontend-java/target/frontend-java-0.0.1-SNAPSHOT.jar
```

## Data and training

```sh
backend-python/.venv/bin/python scripts/sync_f1_data.py --current
backend-python/.venv/bin/python scripts/sync_f1_data.py --season 2025
backend-python/.venv/bin/python scripts/sync_f1_data.py --from 2014 --to "$(date +%Y)"
backend-python/.venv/bin/python scripts/data_quality_report.py
backend-python/.venv/bin/python scripts/build_training_dataset.py --mode PRE_WEEKEND
backend-python/.venv/bin/python scripts/train_models.py --through-season 2025 --mode PRE_WEEKEND
backend-python/.venv/bin/python scripts/train_models.py --through-season 2025 --mode POST_QUALIFYING
backend-python/.venv/bin/python scripts/evaluate_models.py --season 2025 --mode PRE_WEEKEND
```

The explicit 2025 arguments reproduce the documented experiment; omit through-season for the last calendar year dynamically. Train only after confirming data quality. A full historical sync can take minutes and respect source quotas; retries/cache are built in. UI Data actions run sync/training in a background worker and display progress/status. Restarting the backend interrupts that in-process job.

## Test

```sh
backend-python/.venv/bin/python -m pytest backend-python/tests -q
RUN_SELENIUM=1 backend-python/.venv/bin/python -m pytest backend-python/tests/test_odds_parser.py -q
mvn -f frontend-java/frontend-java/pom.xml test package
backend-python/.venv/bin/python scripts/verify_running_app.py --browser
```

Backend tests isolate a temporary database. Chrome/Selenium Manager is needed for the real fixture and browser smoke test. The E2E command needs both live servers and deliberately saves forecast history and manual odds; it does not alter race results.

## Troubleshooting

| Symptom | Check / action |
|---|---|
| Backend unavailable | `/health`, backend terminal, `.venv` dependencies and port |
| macOS port 5000 conflict | Use 127.0.0.1; if necessary set FLASK_PORT=5001 and FLASK_API_BASE_URL=http://127.0.0.1:5001 for Spring |
| Empty current season | Sync current; confirm provider availability and `/data/sync/status` |
| Stale orange notice | Explicitly sync; it means last successful sync is over 24h old |
| No ML model | Backfill at least four seasons and run training; fallback is labelled |
| Past race uses baseline | No model artifact trained strictly before that race exists; do not use the future model |
| After qualifying disabled | Qualifying is not yet available at cutoff; use Pre-weekend. Synchronize after the session. Validation keeps the form visible. |
| Championship rejected | Past scheduled rounds lack verified results; sync first |
| 409 deleting entity | Linked results/entries protect referential integrity |
| Odds rejected | Validate driver field, decimal odds and every timestamp |
| LLM shows template | Integration disabled, credentials/model absent or provider unavailable; this is supported |
| Portrait missing | Local silhouette is the supported fallback |
| UI job disappears | Backend restarted; inspect durable sync history and restart the operation if needed |

## Backup and restore

`backup_database.py` uses SQLite's online backup API and validates integrity. To restore, stop the project's Flask process, preserve a new backup of the current DB, copy the chosen backup over `database/f1.db`, then run migration and quality checks. Do not delete backups or restore over a running database. The original source archive under `database/backups` is recoverable; no Git repository existed in this downloaded workspace, so no Git commit was created.

The configured local deployment has no multi-user authentication, distributed job queue or automatic scheduler. Keep defaults bound to loopback. A production deployment requires a dedicated deployment/security design.

## Automatic News and UI assets

The Flask entry point now starts the Selenium news scheduler (30-minute default) while the application is running. Chrome is required for this feature. Existing model forecasts still work when news collection or the local LLM is unavailable. See [NEWS_PIPELINE.md](NEWS_PIPELINE.md) for setup, status, limits, pause/refresh controls and experimental signal rules.

```sh
backend-python/.venv/bin/python scripts/setup_news_llm.py
backend-python/.venv/bin/python scripts/sync_news.py
backend-python/.venv/bin/python scripts/enrich_driver_portraits.py
backend-python/.venv/bin/python scripts/verify_ui_layouts.py
```

Frontend CSS/JS URLs include a content hash, so a normal page reload fetches updated styles. Do not overwrite a JAR while expecting its running process to reload it: build, then restart the frontend. Circuit geometry is bundled and works offline; official photos require network access and have a local fallback.

## Refresh published weekend sessions

Use Predictions → **Update weekend**. The worker fetches the official event calendar and completed, published session results, recalculates GP/Sprint/championship estimates and reloads the result page. Repeated updates are throttled for 30 seconds. Missing or failed sources retain the previous observations; the screen shows their collection times and an explicit status.

```sh
backend-python/.venv/bin/python scripts/verify_live_weekend.py --race-id 210
```

The example race ID is the verified local Singapore 2026 record; use the selected local race ID on another database. No paid live-timing subscription is needed for published results. Source availability and experimental forecast assumptions are in [LIVE_WEEKEND.md](LIVE_WEEKEND.md).


## Free Race Control

Live public timing and complete historical replay now have a dedicated viewer at `/race-control`, including a separate window. No paid subscription is used. Public live position / car channels can be unavailable; completed-session replay includes measured positions and telemetry. See [RACE_CONTROL.md](RACE_CONTROL.md) for availability, sources, timestamps and verification.


Race Control now includes continuous replay through qualifying intermissions, smooth measured markers / labels, tyre-set and incident panels, and an experimental on-track winner forecast. [Details and verification](RACE_STRATEGY.md). The frame endpoint accepts a bounded `window` in seconds for high-speed replay and includes `race_forecast`, `incidents`, `tyre_estimate` and reported component states.

## Manual session update

Use Tools → **Update all sessions**. Its independent service checks the current weekend and downloads public archives through the original Race Control code. GET/POST `/race-control/api/sessions/refresh` reports the shared job. See SESSION_REFRESH.md for source availability, progress and deduplication. The OCR and separate data-platform pages have been removed.
# Race Control feed verification

Use the unchanged startup commands and Tools → Update all sessions. Feed diagnostics is inside the existing viewer. During the next running session, verify matching identity and dated fresh TimingData, then separately actual Position.z/CarData.z receipt. To run a command-line source probe, stop the app's shared live connection first. See [LIVE_DIAGNOSTICS.md](LIVE_DIAGNOSTICS.md) for commands and [LIVE_INTEGRATION_REPORT.md](LIVE_INTEGRATION_REPORT.md) for status/evidence. Recovery is STALE; config flags do not grant protected-source access. No OCR or separate data-platform page is present.
