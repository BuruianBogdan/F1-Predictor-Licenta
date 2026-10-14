# Feed diagnostics and API

Open the original Race Control viewer and click **Feed diagnostics**. The dialog reports the selected session, provider, source UTC, identity, transport/presentation state and observed channel capabilities. Subscribed but unreceived channels are explicitly MISSING. A post-session keyframe is not LIVE. Missing car telemetry is not displayed as zero speed or DRS OFF.

Backend endpoints, under the existing namespace:

```text
GET  /race-control/providers
GET  /race-control/health
GET  /race-control/{race}/{key}/diagnostics?mode=LIVE|REPLAY&at=UTC
GET  /race-control/{race}/{key}/capabilities?mode=LIVE|REPLAY
GET  /race-control/{race}/{key}/championship-projection?mode=REPLAY&at=UTC&scoring=FULL_DISTANCE|STOPPED_NOW
POST /race-control/{race}/{key}/stop
```

Spring proxies use `/race-control/api` with the same suffix. Existing catalog/prepare/status/frame routes are retained. POST operations retain the project's local/admin-token protection. The diagnostics dialog uses current frame data while playing; opening it also retrieves a fresh diagnostic snapshot. No separate `/live-timing`, `/screen-timing`, `/api/live` or OCR service was restored.

Capabilities can be AVAILABLE, PARTIAL, MISSING, STALE, UNAUTHORIZED or UNSUPPORTED. A disabled channel is UNSUPPORTED; an unobserved enabled channel is MISSING, not proof that access is allowed. Source uncertainty before a probe is UNKNOWN_UNTIL_OBSERVED in the provider catalog. A source refusing the entire public connection is UNAUTHORIZED. Local checkpoints are STALE.

Run the reproducible command-line probe while the desired session is actually running, after stopping any other local feed connection:

```sh
backend-python/.venv/bin/python scripts/verify_live_sources.py --race-id 210 --session R --public-probe --seconds 20
```

Use the actual next race ID/code rather than hardcoding Singapore. Without `--public-probe`, only catalog/cached historical checks run. Reports distinguish TESTED_LIVE, TESTED_HISTORICAL, TESTED_FIXTURE, NOT_TESTED, UNAVAILABLE and ACCESS_NOT_PERMITTED. Fixture tests do not grant source access. The October 11 real public probe received post-session data with absent position/car channels; active live validation remains pending.

## Live Data v2 completion
The existing modal exposes provider/session/meeting/transport/identity, observation and packet UTC, age, requested/available/missing counts, retry attempts, recovery, measured source-to-receipt latency and last error. All twelve topics show requested, valid events, source UTC, age, state and explanation. Colour is accompanied by text. Native dialog Escape/focus and keyboard tower selection are supported.

Source latency belongs to the receipt that advanced that source timestamp; a duplicate later packet does not increase or improve the measurement. Historical archive rows use replay cutoff timestamps and do not imply a live connection. Missing Position.z permits timing without map motion. Missing CarData.z cannot be replaced by calculated telemetry. Recovered checkpoints remain stale until matching fresh dated timing arrives.
