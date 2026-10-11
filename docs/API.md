# REST API

Backend default: `http://127.0.0.1:5000`. Frontend default: `http://127.0.0.1:8090`. Responses are JSON unless an export route specifies CSV/TXT. The routes below are generated from the actual Flask URL map; original endpoint paths remain available.

## Conventions

Prediction probabilities use **fractions [0,1]**, not the old ambiguous percentage field. `win_percentage` explicitly supplies percent for compatibility. Each race response includes mode, model_version, training_cutoff, feature_cutoff, historical_replay, market_factor_used and predictions. Each driver has win/podium/points probabilities, model/market/final winner probability, rank and observed factors.

Errors include `{"error":{"code":"INVALID_INPUT","message":"...","details":{}},"message":"..."}`. 400 indicates invalid input, 404 missing endpoint/entity, 409 conflicting or linked records, 502 provider failure, and 500 an unexpected failure logged server-side. Some service-level missing-data requests return 400. Existing creation endpoints retain their original 200/201 behavior.

Administrative POST routes under `/data/`, `/model/retrain`, `/odds/refresh` and `/explanations/` require `Authorization: Bearer <ADMIN_TOKEN>` if configured, otherwise loopback access. Spring forwards its matching ADMIN_TOKEN. Other legacy routes assume a local deployment.

## Typical operations

`GET /predict/availability?season=...` returns each race’s post_qualifying_available flag, using the same cutoff as inference. Missing qualifying returns backend HTTP 400 with code QUALIFYING_UNAVAILABLE. The frontend disables this mode while unavailable and displays validation messages within the preserved prediction form; actual service failures retain the separate error page.

- `GET /season/context`: active season, verified latest race, future next race, pending results and last successful sync.
- `POST /data/sync/current?background=true`: 202 with job id. Poll `/data/jobs/{id}`. Without background=true, return the completed summary synchronously.
- `POST /data/sync/history`: `{"start_year":2014,"end_year":2026}` starts a background job. Years here are an example; choose the intended range.
- `GET /predict/race/{id}?mode=PRE_WEEKEND`: full persisted forecast. POST_QUALIFYING requires known qualifying. POST_PRACTICE has no learned practice features and falls back explicitly.
- `GET /predict/race/{id}/summary?limit=5`: returns only the requested leading rows; their probabilities do not sum to one because the underlying full field does.
- `POST /predict/race/{id}/market`: `{"mode":"PRE_WEEKEND","odds":[{"driver_id":1,"odds":3.5,"provider":"manual"}],"captured_at":"...UTC..."}`. Use real local driver IDs in that race. Omitting time means submission time; historical replay needs a genuine earlier snapshot. Empty odds preserves model probabilities.
- `GET /predict/championship?simulations=5000&seed=42&season=2026`: structured result, current points, expected final points/position, remaining races and probability. Omit season for dynamic current season. Simulations must be 100–20000. Legacy `/predict/champion` returns just the driver list.
- `GET /model/metrics?mode=PRE_WEEKEND`: full current evaluation; POST_QUALIFYING is also supported. `POST /model/retrain` accepts mode and optional through_season; defaults to last calendar year.
- `POST /scenarios`: name, target_race_id, driver_id and/or constructor_id, pace_delta, reliability_delta, dnf_risk_delta, grid_position and wet_race. Run via `/scenarios/{id}/run` to compare baseline and scenario.
- `POST /explanations/prediction/{run_id}?lang=ro` or `/explanations/race/{id}?lang=ro`: on-demand narrative; source identifies template or openai.
- `GET /prediction-history`: recent 200 displayed runs; SQLite retains older runs. Legacy JSON entries are explicitly unvalidated. `POST /prediction-history/evaluate` distinguishes retrospective replay from genuine pre-race records.

Race/constructor/driver CRUD bodies follow model fields. Updating results or races invalidates result verification until an authoritative resync. Referenced entities cannot be deleted while dependent records remain. Export endpoints generate a current forecast where applicable, not a download of a selected saved run.

GET prediction/export routes preserve the legacy contract and may persist runs. GET dashboard does not. Live odds GET is a compatibility path that can explicitly invoke Selenium if enabled; it is never called by dashboard startup.

## Complete Flask route inventory

| Methods | Path | Handler |
|---|---|---|
| POST | `/circuits` | `circuit.create_circuit` |
| GET | `/circuits` | `circuit.get_circuits` |
| DELETE | `/circuits/<int:circuit_id>` | `circuit.delete_circuit` |
| GET | `/circuits/<int:circuit_id>` | `circuit.get_circuit` |
| PUT | `/circuits/<int:circuit_id>` | `circuit.update_circuit` |
| POST | `/constructors` | `constructor.create_constructor` |
| GET | `/constructors` | `constructor.get_constructors` |
| DELETE | `/constructors/<int:constructor_id>` | `constructor.delete_constructor` |
| GET | `/constructors/<int:constructor_id>` | `constructor.get_constructor` |
| PUT | `/constructors/<int:constructor_id>` | `constructor.update_constructor` |
| GET | `/dashboard/overview` | `dashboard.overview` |
| GET | `/dashboard/stats` | `dashboard.stats` |
| POST | `/data/import` | `import_data.import_data` |
| GET | `/data/jobs/<job_id>` | `intelligence.job` |
| GET | `/data/quality` | `intelligence.quality` |
| POST | `/data/refresh-live` | `odds.refresh_live` |
| POST | `/data/sync/current` | `intelligence.sync_current` |
| POST | `/data/sync/history` | `intelligence.sync_history` |
| POST | `/data/sync/season/<int:year>` | `intelligence.sync_season` |
| GET | `/data/sync/status` | `intelligence.sync_status` |
| POST | `/drivers` | `driver.create_driver` |
| GET | `/drivers` | `driver.get_drivers` |
| DELETE | `/drivers/<int:driver_id>` | `driver.delete_driver` |
| GET | `/drivers/<int:driver_id>` | `driver.get_driver` |
| PUT | `/drivers/<int:driver_id>` | `driver.update_driver` |
| GET | `/drivers/<int:driver_id>/detail` | `intelligence.driver_detail` |
| POST | `/explanations/prediction/<run_id>` | `intelligence.prediction_explanation` |
| POST | `/explanations/race/<int:race_id>` | `intelligence.recap` |
| GET | `/export/champion.csv` | `export.export_champion` |
| GET | `/export/history.csv` | `export.export_history` |
| GET | `/export/metrics.csv` | `export.export_metrics` |
| GET | `/export/race/<int:race_id>.csv` | `export.export_race` |
| GET | `/export/report.txt` | `export.export_report` |
| GET | `/health` | `intelligence.health` |
| GET | `/model/metrics` | `intelligence.model_metrics` |
| POST | `/model/retrain` | `intelligence.retrain` |
| GET | `/odds/<int:race_id>` | `intelligence.odds` |
| GET | `/odds/demo/<int:race_id>` | `odds.demo_odds` |
| GET | `/odds/live/<int:race_id>` | `odds.live_odds` |
| POST | `/odds/refresh/<int:race_id>` | `intelligence.refresh_odds` |
| GET | `/odds/status` | `intelligence.odds_status` |
| GET | `/predict/availability` | `prediction.prediction_availability` |
| GET | `/predict/champion` | `prediction.predict_champion` |
| GET | `/predict/championship` | `intelligence.championship` |
| GET | `/predict/explain` | `prediction.explain_model` |
| GET | `/predict/race/<int:race_id>` | `prediction.predict_race` |
| POST | `/predict/race/<int:race_id>/market` | `prediction.predict_race_with_market` |
| GET | `/predict/race/<int:race_id>/summary` | `prediction.predict_race_summary` |
| GET | `/prediction-history` | `history.list_history` |
| POST | `/prediction-history/evaluate` | `history.evaluate` |
| POST | `/races` | `race.create_race` |
| GET | `/races` | `race.get_races` |
| DELETE | `/races/<int:race_id>` | `race.delete_race` |
| GET | `/races/<int:race_id>` | `race.get_race` |
| PUT | `/races/<int:race_id>` | `race.update_race` |
| GET | `/races/<int:race_id>/detail` | `intelligence.race_detail` |
| GET | `/regulations` | `regulations.get_regulations` |
| POST | `/regulations` | `regulations.save_regulations` |
| POST | `/regulations/reset` | `regulations.reset_regulations` |
| POST | `/results` | `result.create_result` |
| GET | `/results` | `result.get_results` |
| DELETE | `/results/<int:result_id>` | `result.delete_result` |
| GET | `/results/<int:result_id>` | `result.get_result` |
| PUT | `/results/<int:result_id>` | `result.update_result` |
| POST | `/scenarios` | `scenarios.create_scenario` |
| GET | `/scenarios` | `scenarios.list_scenarios` |
| DELETE | `/scenarios/<scenario_id>` | `scenarios.delete_scenario` |
| POST | `/scenarios/<scenario_id>/run` | `scenarios.run_scenario` |
| GET | `/season/context` | `intelligence.season_context` |
| GET | `/standings/constructors` | `standings.get_constructor_standings` |
| GET | `/standings/drivers` | `standings.get_driver_standings` |

## Frontend pages

`/`, `/predictions`, `/championship`, `/standings?season=...`, `/drivers`, `/drivers/{id}`, `/constructors`, `/circuits`, `/races`, `/races/{id}`, `/results`, `/data`, `/model`, `/history`, `/simulator`, `/regulations`, `/export`. The legacy `/import` redirects to Data.

CSV: `/export/race/{id}.csv`, `/export/champion.csv`, `/export/history.csv`, `/export/metrics.csv`; plain text: `/export/report.txt`. These are backend URLs, linked from the frontend Export page.

## News and circuit calendar

- `GET /calendar?season=2026` returns upcoming, completed, pending and changed rounds plus per-race SVG geometry; omitted season uses the active season.
- `GET /drivers/grid` returns the current season driver portrait grid.
- `GET /news` returns short, attributed briefs with model/source provenance and extracted signals; never returns raw source excerpts.
- `GET /news/status` returns schedule, local model status and recent crawler runs.
- `POST /news/refresh` queues a crawler/rewrite job (202); `POST /news/automation` changes the persisted enabled flag and interval. Both use admin/local protection.

Race responses now include `base_model_probability`, `news_adjusted_probability`, `news_delta` and `news_signals` per driver, plus top-level `news_factor_used`, `news_signal_ids` and `news_cutoff`. `win_probability` incorporates eligible experimental news; `model_probability` retains the underlying model value; `final_probability` additionally includes optional market blending. Championship responses include `news_adjusted_races`. Existing official results/standings are unchanged. See [NEWS_PIPELINE.md](NEWS_PIPELINE.md).

## Published weekend updates and Sprint

- `GET /weekend/<race_id>` returns local session availability, leaders, official source links and saved forecasts.
- `POST /weekend/<race_id>/refresh` queues a protected update-and-recalculate job (202).
- `GET /predict/live/<race_id>?target=RACE|SPRINT` computes from stored versioned observations without network calls.
- `GET /predict/sprint/<race_id>?mode=LIVE|PRE_WEEKEND` returns a separate Sprint prediction.
- `GET /predict/race/<race_id>?mode=LIVE` returns the current GP estimate.

New response fields include `target`, `event_start_at`, `base_feature_cutoff`, `session_probability`, `session_evidence`, `session_snapshot_ids`, `session_components`, `expected_points` and `points_places`. A target that has started cannot receive a new pre-event forecast. Full details: [LIVE_WEEKEND.md](LIVE_WEEKEND.md).


## Free Race Control

Live public timing and complete historical replay now have a dedicated viewer at `/race-control`, including a separate window. No paid subscription is used. Public live position / car channels can be unavailable; completed-session replay includes measured positions and telemetry. See [RACE_CONTROL.md](RACE_CONTROL.md) for availability, sources, timestamps and verification.


Race Control now includes continuous replay through qualifying intermissions, smooth measured markers / labels, tyre-set and incident panels, and an experimental on-track winner forecast. [Details and verification](RACE_STRATEGY.md). The frame endpoint accepts a bounded `window` in seconds for high-speed replay and includes `race_forecast`, `incidents`, `tyre_estimate` and reported component states.
