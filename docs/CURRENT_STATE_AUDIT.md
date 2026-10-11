# Current state audit — 7 October 2026

## Scope and preservation
Inspected local Python/Java source, routes, models, repositories, importers, ML modules, all templates/assets, SQL, scripts, configuration, README and SQLite. This directory is a downloaded checkout **without .git**; git status cannot report changes. Local files are authoritative. Source snapshot and a SHA256 inventory are saved before implementation. No .env was present. Never copy secrets to documentation.

## Actual architecture and dependency map
Spring Boot 3.3.5 / Java 17 target; installed runtime Java 21. Package `com.f1predictor.frontendjava`, rooted at `frontend-java/frontend-java`. UI port **8090**, Flask **5000**. Existing servers were already running. Root .venv has no dependencies; backend-python/.venv is the application environment.

| Spring controller → client | Flask route → service → repository | ORM/table |
| --- | --- | --- |
| CrudController → FlaskApiService | /drivers → DriverService → DriverRepository | Driver/drivers |
| CrudController → FlaskApiService | /constructors → ConstructorService → ConstructorRepository | Constructor/constructors |
| CrudController → FlaskApiService | /circuits → CircuitService → CircuitRepository | Circuit/circuits |
| CrudController → FlaskApiService | /races → RaceService → RaceRepository | Race/races |
| CrudController → FlaskApiService | /results → ResultService → ResultRepository | RaceResult/race_results |
| CrudController → FlaskApiService | /standings/* → StandingsService → StandingsRepository | results + identity tables |
| DashboardController → both clients | /dashboard/overview, /predict/champion | repository reads + prediction JSON |
| PredictionController → PredictionApiService | /predict/* → PredictionService; optional ml/* | all results, no cutoff |
| ImportController → FlaskApiService | /data/import, /data/refresh-live → ImportService | all five ORM tables |
| RegulationController → FlaskApiService | /regulations → RegulationService | regulation_parameters.json |
| SimulatorController → FlaskApiService | /scenarios → ScenarioService | scenarios.json |
| HistoryController → FlaskApiService | /prediction-history → HistoryService | prediction_history.json |
| ExportController → browser links | /export/* → ExportService → PredictionService | CSV/TXT |

Frontend routes: /, /drivers, /constructors, /circuits, /races, /results, /standings, /import, /predictions, /regulations, /simulator, /history, /export. CRUD screens are read-only lists; REST CRUD exists. Backend routes additionally include entity GET/POST/PUT/DELETE, /dashboard/stats, /predict/explain, /predict/race/{id}/summary and /market, /odds/demo/{id}, /odds/live/{id}, /regulations/reset, /scenarios/{id}/run, /prediction-history/evaluate.

## SQLite before migration
65 drivers, 18 constructors, 33 circuits, **216 races, 1,000 results**. Seasons 2017–2026. Races by year: 20,21,21,17,22,22,22,24,24,23. Every season has **exactly 100 results**: importer ignores Jolpica's capped pagination. Some race fields are truncated halfway. All 216 races marked completed; **165 have no results**, **7 are in the future** at audit time. No duplicate (race,driver)/(season,round), no orphan result references, no null grid/position. Identity refs have UNIQUE constraints; result references have no FK constraints. No season entries, qualifying, sprints or official standings. Existing 159 JSON prediction runs are retained but scientifically invalid/legacy because of leakage.

## Confirmed defects
- Both prediction branches use target finishing position/points/status; aggregates and Elo include future races. `ml` is another weighted heuristic, not a trained estimator.
- No chronological validation, calibration, saved model or measured honest metrics.
- Result ordering uses database IDs, which are not chronological (2017 was imported after 2025).
- Championship uses lifetime points, including retired drivers; standings aggregate all seasons.
- Dashboard chooses the last race when every race is marked completed, calling it next race.
- Import uses insert-if-absent; cannot update corrections/calendar changes, no pagination, retries, custom User-Agent, sync history or partial-data checks.
- Current refresh hardcoded to 2025; import defaults end in 2024; predictions hardcoded race ID 1.
- Malformed unused schema.sql: forname/seazon_year/results_id and trailing comma.
- FastF1 loops entire season, relative cache, suppresses session failures, float-to-int check fails.
- Market percentages shrink when no odds; missing/invalid odds silently disappear; no timestamps.
- JSON prediction history loses old runs after 200; exceptions swallowed. Dashboard creates predictions on every view.
- Uniform regulation multiplier cancels under normalization; scenario changes score but not probability.
- Selenium is a template. No LLM service, no health endpoint, no backend tests. Spring only contextLoads.
- Java HTTP client has no timeouts; one client hides outages as empty data, the other can show server errors.
- No dynamic winner/race detail/driver detail/media or model page. RO/EN applies to seven nav labels only.
- backend-python/ui is an unused static prototype with hardcoded sample dates/data. Preserve as legacy only; not served.

## Implementation sequence
1. SQLite online backup and source snapshot (before changes).
2. Environment configuration, versioned additive migration, integrity constraints, explicit provenance, safe completion logic.
3. Jolpica provider with pagination and resilient I/O; atomic, idempotent season sync; cached optional FastF1/OpenF1. Season context/quality report.
4. Pre-race cutoff feature pipeline, named heuristic baseline, sklearn estimator and chronological holdouts/calibration, reproducible championship Monte Carlo.
5. Persisted prediction runs, truthful replay evaluation, timestamped optional manual/Selenium odds and optional cached LLM explanations.
6. Preserve routes/package/use cases, redesign Spring views around race intelligence and generic winners; improve error handling, theme/i18n.
7. Backend regression tests, local Selenium fixture, frontend render/build tests, run both servers, record actual metrics and limits in docs.
