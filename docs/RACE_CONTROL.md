# Race Control: free public timing and real session replay

Open `/race-control`, or use **Live / replay timing** on the calendar / race center. Every race detail has a Race Control button. Pick FP1, FP2, FP3, Sprint Qualifying, Sprint, Qualifying or Grand Prix when those sessions exist in the real schedule. Coverage of the OpenF1 archive starts in 2023.

## What is available without payment

- **Historical replay:** measured positions for every driver, timing order, race intervals, best / last laps, tyre compound and age, selected driver’s sectors, personal / session bests, ideal lap, car speed / gear / pedal traces, Race Control messages, circuit weather and announced rain risk. Play, pause, seek and change playback speed. Position animation interpolates between approximate measured samples; lateral wheel-to-wheel placement is not available. The timing tower supplies position changes.
- **Public live timing:** an unauthenticated connection to the Formula 1 SignalR endpoint, using the public protocol supported by FastF1. No account, token, subscription, payment or proxy workaround. The probe after Singapore Sprint Qualifying returned 22 drivers, timing, tyres, weather, track status and race messages. **It did not return Position.z or CarData.z.** Those channels are subscribed to, but dots / telemetry are displayed only if the public source actually sends them. Missing channels are explicitly marked, with full replay offered after the session. Public access can fail or be partial; a later probe returned an unavailable response. An active session has not yet happened during our verification.

The official [FastF1 client source](https://github.com/theOehrly/Fast-F1/blob/main/fastf1/livetiming/client.py) describes unauthenticated access as potentially empty or partial. The [OpenF1 archive](https://openf1.org/docs/) is free; its separate paid live product is **not used**. There is no credential setup for this feature.

## Timing and availability

The catalog discovers session keys by the selected race’s GP date and meeting identity. It does not guess season session IDs. Future sessions show local start time and a countdown; the backend also rejects live preparation before the scheduled start. SignalR SessionInfo must match the exact session key before any update is accepted. A feed still pointing at another session gives an explicit waiting message.

One backend connection is shared by all viewers of the same session. Live frames use a small position buffer. A feed without new packets is marked delayed; interrupted connections reconnect. An actual running session can extend beyond its published time. Completed replay uses actual SESSION STARTED / FINISHED timestamps, so delayed and suspended races are not truncated at their scheduled end. The archive loader reads through five minutes after the actual finish. Incomplete old position caches are reloaded.

Replay laps, sector bests, flags, tyre changes and weather are filtered by the replay timestamp. Deleted laps are matched by driver and published lap duration because message lap numbers can differ from telemetry numbering. Missing values remain unavailable. Qualifying order uses provider positions to preserve elimination / Q1–Q3 progression. Practice / qualifying gaps compare lap times; race intervals come from the interval feed. Provisional P1 is never used as a confirmed race winner.

Public timing supplies current fields but not a full trustworthy past lap history. Live sector history is collected after connection; earlier history is available in replay. Unknown sectors are not reconstructed from a last-lap total. Public live snapshots have an observed / received timestamp; archived weather has its source timestamp.

## Presentation and separate window

The track sits to the left, the selected driver to the right; the timing tower and messages remain in bounded scrolling panels. Driver colours, photos and geometry are driven by actual data. Names remain close to their own dots, slightly ahead in the measured direction; overlapping chips are accepted instead of relocating names. Chips and dots both select the driver. **Separate window** starts an independent viewer at the same replay time and chosen driver, automatically loading the session. It continues when the main tab is closed, while the local servers remain running. Full screen is also supported.

The opening transition uses `Race starts!` for a race / sprint and `Session starts!` for other sessions. Joining an already running session uses `Live timing`. The finish transition uses `Race winner` for races / sprints, `Session leader` for practice / qualifying, and the confirmed driver’s image and name. The user’s supplied cinematic background is used unchanged. Reduced-motion preferences are respected.

Yellow / red / SC / VSC messages are displayed from the source. Local yellow sectors are tracked individually until CLEAR; an incident is not described as a driver injury. Wind from OpenF1 is m/s, converted to km/h. Rain risk is the official Race Control percentage, when provided. No rainfall does not prove dry asphalt; wet / damp / dry is shown only when explicitly reported. There is no unsupported certainty about upcoming rain.

## Runtime and endpoints

Dependencies: standard backend requirements plus `signalrcore`; no browser crawler is used for this feed. Selenium only verifies UI behavior. Caches under `backend-python/data/cache/race-control/` are ignored runtime data. No database schema / forecast feature changes are needed.

Backend:

- `GET /race-control/{race_id}/catalog`
- `POST /race-control/{race_id}/catalog` refreshes metadata.
- `POST /race-control/{race_id}/{session_key}/prepare` with `{"mode":"REPLAY"}` or `{"mode":"LIVE"}` starts preparation.
- `GET /race-control/{race_id}/{session_key}/status?mode=REPLAY` shows progress.
- `GET /race-control/{race_id}/{session_key}/frame?mode=REPLAY&at=UTC_UNIX_SECONDS&driver=63` returns timestamp-filtered state and a short window of actual positions.

The browser accesses the Java same-origin JSON proxy under `/race-control/api/…`. Preparation POSTs retain the existing local / admin protection. Downloads use a global 2.1-second request spacing to respect OpenF1’s free quota; selected-driver telemetry is loaded asynchronously and failed downloads back off. First replay download can take a minute; repeated visits reuse the local cache. Background preparation is independent of the browser tab. Restarting the backend interrupts active preparation / live connections.

## Verification

Run:

```sh
backend-python/.venv/bin/python -m pytest backend-python/tests -q
mvn -f frontend-java/frontend-java/pom.xml test package
backend-python/.venv/bin/python scripts/verify_race_control.py
```

The browser verification uses real Singapore FP1 telemetry. It checks moving dots, the actual yellow / clear events, driver selection, lap sectors, car telemetry, future start gating, five widths from 320 to 1920px, the correct practice-leader transition, and replay continuing in a separate window after the original window closes. See `RACE_CONTROL_VERIFICATION.json` and `screenshots/race-control-*.png`. The delayed last GP replay verifies that final classification / winner transitions remain reachable beyond the original scheduled end.


## Replay and strategy update

The SQ phase-end playback bug and short position buffer at high replay speeds have been corrected. The viewer now adds a tyre-set wear estimate, reported incident / component state and an experimental in-race strategy forecast. See [RACE_STRATEGY.md](RACE_STRATEGY.md) for formulas, source limits and regression verification.

## Measured start / finish and pit lane

The map adds a checkered start / finish line and a separate cyan pit-lane route, with PIT IN / PIT OUT markers. `track_geometry_service.py` works in the same measured Cartesian coordinate system as the dots for every available circuit. The timing line is interpolated at the reference flying-lap start, rather than using an arbitrary geographic polygon vertex. OpenF1 lap-start times and positions are approximate; the marker is labelled accordingly.

A pit path comes from a complete archived pit passage, including the measured branches back to the main course. It must have continuous samples and a distinguishable separation from the reference lap. Unknown / incomplete geometry stays unavailable; a parallel imaginary pit lane is never drawn. Live viewers can inherit landmarks from an earlier completed session at the same meeting. This is static reference geometry, not future timing or strategy information.

Archived PIT status comes from the driver’s latest measured location relative to that route. The archive duration record is a completion record in the verified sessions; treating it as an entry trigger incorrectly kept a car marked PIT after leaving. The entry estimate now scans only past positions, stops at telemetry gaps and never uses a future stop’s duration. Unknown or stale positions leave pit occupancy unavailable. Live continues using the source’s InPit flag.

`verify_track_landmarks.py` checks actual Singapore FP1 / SQ and Malaysian GP start / pit paths, clickable labels following their own moving dots, pit occupancy and five viewport widths. See `TRACK_MAP_VERIFICATION.json` and `screenshots/race-control-attached-labels.png`. Geometry unit tests cover missing measurements, no fabricated lane, past-only pit state, stale samples and a timing line distinct from the arbitrary shape origin.
