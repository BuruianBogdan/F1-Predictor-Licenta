# Model card

## Intended use

Local Formula 1 research and comparative prediction analysis. A probability is not a guarantee. The language model and optional bookmaker feed are separate from this model. No profitability or prospective season-wide accuracy is claimed.

## Data and provenance

Jolpica historical race results, qualifying and sprints; 2014–2025 for this training experiment, with synchronized 2026 data reserved for current inference. Final corrected results and reconstructed race entry lists are used. Upcoming participants are projected from the latest known field when no target entry list exists. Historical results may reflect corrections not available at the original prediction time; reconstructed entrants can introduce selection bias. Newly entering drivers use documented prior defaults.

Production classifier fit: **2014–2024**. Calibration: **2025**. Historical holdouts: **2022–2025, 92 races**. For a test season T, fit uses seasons through T−2, and T−1 calibrates. No test outcome is used to fit that fold's classifier/calibrator. The production algorithm was preselected logistic regression; boosting is a benchmark, not the result of optimizing on these holdouts.

## Measured aggregate results

Metrics below are weighted averages of per-season metrics by race count; each fold retains its own row counts and calibration bins. These are retrospective walk-forward results, not deployed predictions collected before those races.

| Mode | Model | Top 1 | Top 3 coverage | Podium P/R | MAE | Spearman | Brier | Binary log loss | Race log loss | ECE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| POST_QUALIFYING | baseline | 53.26% | 81.52% | 0.6051 | 3.5506 | 0.6291 | 0.03247 | 0.11105 | 1.44127 | 0.02157 |
| POST_QUALIFYING | logistic | 51.09% | 85.87% | 0.6594 | 3.2716 | 0.6704 | 0.03000 | 0.10273 | 1.30558 | 0.02449 |
| POST_QUALIFYING | hist_gradient_boosting | 57.61% | 89.13% | 0.6413 | 3.6118 | 0.6149 | 0.03006 | 0.10937 | 1.40512 | 0.02585 |
| PRE_WEEKEND | baseline | 45.65% | 72.83% | 0.5326 | 3.8936 | 0.5776 | 0.03642 | 0.12641 | 1.68684 | 0.01829 |
| PRE_WEEKEND | logistic | 50.00% | 79.35% | 0.5725 | 3.8910 | 0.5772 | 0.03415 | 0.12278 | 1.63880 | 0.02801 |
| PRE_WEEKEND | hist_gradient_boosting | 52.17% | 71.74% | 0.5326 | 4.0623 | 0.5486 | 0.03673 | 0.13968 | 1.90649 | 0.03104 |

Top 1: predicted favourite wins. Top 3 coverage: actual winner appears among the top three predictions. Podium precision/recall: overlap between predicted and actual podium sets; both sets have three drivers. MAE/Spearman compare complete rankings derived from win probability. Brier and binary log loss are measured over driver win labels; race log loss is the negative log probability of the actual winner. ECE uses ten fixed-width probability bins and is dominated by the many low-probability drivers.

Calibration does **not** establish perfect reliability. Logistic ECE is worse than baseline in both modes; post-qualifying Top 1 is also lower than baseline. No confidence intervals, statistical significance test, ablation study or nested hyperparameter search is claimed. These are appropriate next experiments. Normalization and monotonic correction occur after sigmoid calibration and can alter calibration; the reported metrics measure the final output.

## Fold results

| Mode | Test season | Classifier fit seasons | Calibration season | Races | Baseline Top 1 | Logistic Top 1 | Logistic Brier |
|---|---:|---|---:|---:|---:|---:|---:|
| POST_QUALIFYING | 2022 | 2014–2020 | 2021 | 22 | 40.91% | 50.00% | 0.03071 |
| POST_QUALIFYING | 2023 | 2014–2021 | 2022 | 22 | 90.91% | 86.36% | 0.01060 |
| POST_QUALIFYING | 2024 | 2014–2022 | 2023 | 24 | 45.83% | 41.67% | 0.04346 |
| POST_QUALIFYING | 2025 | 2014–2023 | 2024 | 24 | 37.50% | 29.17% | 0.03368 |
| PRE_WEEKEND | 2022 | 2014–2020 | 2021 | 22 | 40.91% | 59.09% | 0.03301 |
| PRE_WEEKEND | 2023 | 2014–2021 | 2022 | 22 | 90.91% | 86.36% | 0.01565 |
| PRE_WEEKEND | 2024 | 2014–2022 | 2023 | 24 | 25.00% | 37.50% | 0.04661 |
| PRE_WEEKEND | 2025 | 2014–2023 | 2024 | 24 | 29.17% | 20.83% | 0.03970 |

## Model artifacts

- `logistic-sigmoid-v2-post_qualifying-through-2025`: trained `2026-10-07T07:57:25.421744+00:00`; data interval `2014-03-16` to `2025-12-07`; eligibility cutoff `2025-12-08T00:00:00+00:00`.
- `logistic-sigmoid-v2-pre_weekend-through-2025`: trained `2026-10-07T07:37:17.198535+00:00`; data interval `2014-03-16` to `2025-12-07`; eligibility cutoff `2025-12-08T00:00:00+00:00`.

Generated joblib files and datasets are local under backend-python/data and excluded from source control. JSON reports under docs/evaluation preserve the measured experiment; they are snapshots and do not automatically update when the user retrains. The API reads the current reports under data/models. Historical artifacts are selected by training cutoff; absent/ineligible artifacts produce an explicit heuristic fallback. Only load trusted local joblib files.

## Features and labels

Winner is position 1, podium is classified position ≤3, points_finish is classified position ≤10. The latter is a top-ten label, which does not capture shortened-race exceptions, disqualification timing or every historical scoring rule. Starts are counts of available prior result records, not an independent start-status archive. Driver/constructor identities are metadata; numeric feature inputs are:

- `races_started_before_target`
- `season_points_before_target`
- `championship_position_before_target`
- `avg_finish_last_3`
- `avg_finish_last_5`
- `avg_finish_last_10`
- `points_last_3`
- `points_last_5`
- `points_last_10`
- `podiums_last_5`
- `wins_last_10`
- `finish_rate_last_10`
- `dnf_rate_last_10`
- `position_trend`
- `points_trend`
- `driver_circuit_avg_finish`
- `driver_circuit_previous_results`
- `constructor_points_before_target`
- `constructor_championship_position`
- `constructor_avg_finish_last_3`
- `constructor_avg_finish_last_5`
- `constructor_points_last_5`
- `constructor_podium_rate`
- `constructor_dnf_rate`
- `constructor_momentum`
- `qualifying_position`
- `qualifying_known`
- `grid_position`
- `grid_known`
- `round_number`
- `regulation_era`
- `circuit_dnf_rate`

The factual grid placeholders are always unknown; only qualifying availability gates actual qualifying values. Practice mode has no trained estimator. Historical qualifying/sprint availability is approximated conservatively from scheduled timestamps. No target race finishing position, points, status, grid, fastest lap or future race result is an input. Regression tests mutate those records and check invariance.

## Unsupported or limited claims

- No ML+market benchmark: archived pre-race odds are unavailable. Functional odds tests prove normalization and time checks, not improvement.
- No learned practice, weather, tyre, telemetry, strategy, safety-car, replacement or regulation-change effect.
- Form is held fixed in championship simulation; reliability draws are independent and full points are assumed.
- Win-probability ordering may rank the midfield poorly. Podium/points are monotonic marginals, not a joint permutation distribution, and sums need not equal 3/10.
- A major new regulation era is distribution shift; the numeric era feature is not evidence that its effect has been learned.
- What-if grid/weather/regulation changes are documented sensitivity assumptions, not validated causal effects.
- Historical driver portraits/team colours use the latest media snapshot and may differ from historical appearance.

Full reports: [pre-weekend](evaluation/metrics-pre_weekend.json), [post-qualifying](evaluation/metrics-post_qualifying.json). Method implementation: [prediction methodology](PREDICTION_MODEL.md).

## Experimental news overlay

Live race forecasts may apply a bounded, explicitly assumed penalty weight from eligible official news. Publication **and actual collection** must precede the mode's cutoff; no new story can contaminate an older replay. This overlay is separate from the 32 learned features and is **not included in the accuracy metrics above**. It has not been backtested and should not be described as improving accuracy. The LLM writes summaries only. [NEWS_PIPELINE.md](NEWS_PIPELINE.md) specifies extraction, deduplication, timing, weight caps and Monte Carlo integration.

## Weekend and Sprint estimates

The delivered Update weekend flow uses a bounded evidence mixture on top of the existing GP historical prior. Practice, Sprint Qualifying, actual Sprint, GP Qualifying and published grids are kept distinct and dated. Sprint points/reliability and GP points/reliability have separate treatment. This is a new **experimental overlay and GP-prior-based Sprint estimate**; the earlier trained-model metrics do not validate it. Parameter assumptions and required future backtesting are documented in [LIVE_WEEKEND.md](LIVE_WEEKEND.md).


## On-track strategy model

`on-track-strategy-v1` is a separate experimental finish-time simulation from current race gaps, clean pace, tyre age and estimated future stops. It updates in Race Control during live timing or replay. It has not been calibrated or backtested; the baseline logistic classifier metrics above do not apply. Wear percentages are a model index for the set, not sensor measurements. See [RACE_STRATEGY.md](RACE_STRATEGY.md).
