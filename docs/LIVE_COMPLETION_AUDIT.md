# Live Data v2 completion audit

Workspace: `/Users/bbg/Downloads/F1-Predictor-ISS-Final`. Initial HEAD `710b7e34ed70161f97a1e1adcc37e02d06cbe89e`, initial branch `main`, completion branch `fix/live-feed-completion`. No commit or push performed. The nested `F1-Predictor-Licenta` checkout was not modified.

The reference commit contains the Python integration, not the frontend/docs. The local workspace already contained uncommitted Java proxy, Thymeleaf diagnostics/projection, scripts and documentation. They were preserved and extended. An audit of GitHub HEAD alone therefore describes a different state from this working tree.

| Finding | Implemented correction / evidence |
|---|---|
| STOPPED_NOW caused an extra projection fetch per frame | Scoring travels through the existing Java/Flask frame route; UI consumes embedded diagnostics/projection. Browser request inventory verifies no duplicate diagnostics/projection calls. |
| Diagnostics omitted useful fields | Meeting, reconnect attempts, observed/received UTC, age, recovery, measured latency, errors, requested topics and channel explanations are visible. |
| Projection omitted team and movement | Backend provides current entrant team; both tables show movement and distinguish official/session/total points. |
| Requests could remain pending indefinitely | 20-second AbortController timeout, session generation invalidation, pagehide cancellation and visible errors. |
| Finalised + P1 treated as confirmed | Public frame no longer sets a winner from transport finality. Result evidence is read from versioned published classifications. |
| Legacy GP results had no publication time | Replay baseline excludes unversioned results and withholds totals; live can use already verified local prior results, with scope documented. No historical timestamp is invented. |
| Later sync overwrote published results | Existing weekend snapshot table now records Jolpica GP/Q/Sprint corrections with actual local observation UTC; SQL schema is unchanged. |
| Checkpoint temporary filename could collide | Unique temporary files, atomic replace, synchronized pruning, size/age/future-time/context checks and diagnostic whitelist. |
| Benchmark used a reconstructed pre-race model | Baseline now requires a genuinely saved, non-replay forecast created with training/features before session start. Missing saved forecasts are reported unavailable. |
| Source probe labels were ambiguous | VERIFIED_HISTORICAL / VERIFIED_FIXTURE / NOT_TESTED and PENDING_LIVE_SESSION are explicit. Historical browser script no longer invents a live probe. |

Existing Race Control, SVG map/labels/interpolation, replay, telemetry, sectors, strategy, incidents, news, dashboard, calendar, predictions and Tools Update all sessions remain. Removed OCR and separate data-platform pages remain removed. No new independent live proxy, React app or authenticated F1 TV collection was introduced.

Evidence and exact commands/results: [completion report](LIVE_COMPLETION_REPORT.md), [real browser regression](RACE_CONTROL_VERIFICATION.json), [UI fixture scenarios](LIVE_COMPLETION_BROWSER.json), [FastF1 experiment](FASTF1_ARCHIVE_VERIFICATION.json), [source probe](LIVE_SOURCE_VERIFICATION.json), [evaluation](evaluation/LIVE_BACKTEST_RESULTS.json). Active-session validation is a separate pending acceptance item.
