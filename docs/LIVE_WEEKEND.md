# Published weekend updates and sprint forecasts

## User flow

Open Predictions, select a race and Grand Prix or Sprint, then press **Update weekend**. The background job reads the official event schedule and the latest published classifications, saves immutable observations, and recalculates Grand Prix, sprint (when still upcoming) and championship forecasts. The page shows progress and automatically reloads the result after completion. Repeat after the next session. The dashboard and championship page show the latest saved weekend estimates. A 30-second cooldown prevents duplicate rapid fetches.

This is an on-demand update of published results after sessions, rather than an in-session telemetry stream. The public official results source requires no paid API credentials. OpenF1's real-time access during sessions has a separate sponsor/authentication requirement; it is not silently assumed to be available.

The interface shows each scheduled session, leader, time/gap, full classification, source link and observation time. Session cards follow the real official calendar. A sprint weekend such as Singapore 2026 has FP1, Sprint Qualifying, Sprint, Qualifying and Race; FP2/FP3 are not fabricated. Ordinary weekends can contribute FP1/FP2/FP3.

## Data and identity

`OfficialWeekendProvider` discovers the selected event's official results URL from the season index and matches its event name and Grand Prix date. It uses official SportsEvent structured metadata for UTC session start/end times and public classification tables for positions, laps, points and timing. A mismatched event/date is rejected. Separate page headings prevent a Sprint Qualifying table from being accepted as a confirmed Sprint Grid.

Practice rows reconstruct absolute times from the leader's lap plus each displayed gap. Qualifying segment times remain separate; classification position is used for grid expectations because Q1/Q2/Q3 times are not directly comparable. Driver codes are matched against the known race field, not database IDs guessed from race numbers. Incomplete or ambiguous classifications are not used. Official Sprint points are ingested only from a completed published points table.

Migration 3 adds `weekend_session_snapshots` and `weekend_states` after a database backup. Each changed classification creates a new immutable snapshot with source URL, session interval, collection timestamp, hash and normalized rows. Repeated identical refreshes preserve the first observation timestamp and do not duplicate a snapshot. Failure retains previous observations and the previous successful forecast.

Predictions use the latest eligible snapshot of each session at their explicit cutoff. Both collection time and session completion must precede the cutoff and the target event. A later refresh cannot enter an older forecast. New forecasts are blocked after the target begins; the saved pre-event prediction can still be inspected.

## Calculation

The existing calibrated **Grand Prix historical model** supplies the prior, using its unchanged pre-weekend feature cutoff and temporally eligible training artifact. Weekend observations are a separate explicit mixture. They are not silently added as untrained columns to the model, and original walk-forward accuracy does not describe this new overlay.

Evidence distributions are normalized within a session and mixed with the prior:

| Evidence | Grand Prix mixture weight | Sprint mixture weight |
|---|---:|---:|
| Practice pace, all available sessions combined | 0.10 | 0.10 |
| Sprint Qualifying classification | 0.12 as pace evidence | 0.72 as provisional sprint grid |
| Published Sprint Grid | — | 0.72, supersedes Sprint Qualifying |
| Actual Sprint classification | 0.12 | Never used to predict that same sprint |
| Grand Prix Qualifying | 0.62 as provisional GP grid | Excluded |
| Published GP Starting Grid | 0.67, supersedes GP Qualifying | Excluded |

Total session mixture weight is capped at 0.85; the historical prior retains the remainder. Practice averages FP1/FP2/FP3 with recency weights 1/2/3. Its pace distribution uses `exp(-within_session_gap_seconds / 0.8)` with capped outlier gaps. Classification/grid distributions use `exp(-beta*(position-1))`; actual Sprint results additionally multiply that evidence by the historical prior before normalization so a winning result reinforces existing strength rather than flattening it. Beta: beta 0.18 for sprint grid, 0.14 for qualifying/GP grid, 0.12 for sprint results. Missing observations retain their prior probability mass. Fuel and tyre programmes are not inferred from ranking.

These are **experimental assumptions, not fitted parameters or an accuracy improvement claim**. Sprint uses a GP-strength prior; no separately trained sprint model is claimed. A pole or practice lead changes the distribution without forcing that driver to win.

Current eligible news applies to GP only. A published GP grid supersedes the news penalty weight to avoid counting a grid penalty twice. GP engine-penalty news does not affect Sprint probabilities.

A seeded finish simulation provides podium probability, points-finish probability (top 8 for Sprint, top 10 for GP) and expected points. Full-distance GP awards are 25/18/15/12/10/8/6/4/2/1; Sprint awards 8/7/6/5/4/3/2/1. Retirement draws are independent. The GP finish prior is clamped to 0.10–0.995 to avoid certainty from a short history. The sprint finish prior uses this GP prior to the power 1/3, an explicit constant-distance hazard assumption for roughly one-third race distance.

Championship Monte Carlo uses distinct Sprint and GP forecasts when observations are available. Confirmed new Sprint points after an official standings snapshot are added once; a newer standings snapshot absorbs them and stops that addition. Sprint wins do not increment GP victory countback. If a sprint has started but results are unverified, championship simulation waits rather than dropping or duplicating its points.

## Provenance and review

Every saved forecast records target, event start, live observation cutoff, original baseline feature cutoff, snapshot IDs, mixture components, driver evidence and model version. The UI compares the previous saved forecast with the latest update in percentage points. Live GP and Sprint history records are separate; their eventual evaluations use the corresponding classification, never GP results to score a Sprint prediction.

`model_version` carries a `+weekend-v1` suffix and `model_type=weekend_evidence_mixture`. Baseline probabilities, session mixture probabilities and final probabilities remain visible through the tabs. The local LLM does not generate timing data or numerical probabilities.

## API and CLI

- `GET /weekend/<race_id>`: local schedule, observations, status and last saved bundle.
- `POST /weekend/<race_id>/refresh`: local/admin-protected background job, HTTP 202.
- `GET /predict/live/<race_id>?target=RACE|SPRINT`: calculate from cached eligible observations, no network fetch.
- `GET /predict/sprint/<race_id>?mode=LIVE|PRE_WEEKEND`: separate sprint forecast.
- `GET /predict/race/<race_id>?mode=LIVE`: GP weekend estimate.
- `GET /data/jobs/<id>`: progress/status of the update job.

References: [official Singapore schedule](https://www.formula1.com/en/racing/2026/singapore), [official FP1 results](https://www.formula1.com/en/results/2026/races/1296/singapore/practice/1), [official Sprint Qualifying results](https://www.formula1.com/en/results/2026/races/1296/singapore/sprint-qualifying), [OpenF1 access documentation](https://openf1.org/).
