# Data pipeline

## Initial defects and recovery

The old importer requested an oversized results page but Jolpica returned 100 records; it did not paginate. Thus each old season contained exactly 100 results and many imported races were incorrectly completed. Migration cleared unverified completion flags, preserved IDs/history, and a full synchronization verified complete result payloads. Pre-upgrade SQLite and source snapshots are retained locally under `database/backups`.

## Providers

| Provider | Implemented responsibility | Live verification on 2026-10-08 |
|---|---|---|
| Jolpica | Calendar, identities, results, qualifying, sprints, official driver/constructor standings | Seasons 2014–2026 imported; current season refreshed twice without duplicate facts |
| FastF1 | Explicit cached schedule/session results, weather, optional laps/tyres and telemetry loading | Latest completed race session R: 22 results, 254 weather samples; telemetry disabled |
| OpenF1 | Optional portraits and team colours keyed to known driver identity | Completed session 11731: 22 driver media records updated |
| Selenium | Optional external decimal odds only | Local Chrome fixture passed; no real bookmaker configured |

[Jolpica API documentation](https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md) describes the structured API and pagination. [Rate limits](https://github.com/jolpica/jolpica-f1/blob/main/docs/rate_limits.md) must be respected. FastF1 and OpenF1 enrichment never determine race completion and never run on application startup.

## Synchronization contract

1. Acquire provider payloads with a custom `F1Predictor/2.0` User-Agent, timeouts, bounded HTTP retries, request spacing, raw-response cache and page traversal using returned limits/offsets.
2. Validate structure and calendar identity. Reject future result payloads, duplicate drivers and implausibly short classifications.
3. Within one transaction per season, upsert identities and `(season, round)` races, race-aware entries, results, qualifying and sprints, then official standings.
4. Mark completed only when a valid result set has been received for a past start. A scheduled date passing alone does not imply completion.
5. Record SUCCESS or FAILED with timestamps and counts in data_sync_runs. Roll back seasonal facts on failure.

Corrections update existing records. Two standing snapshot updates during an otherwise unchanged repeat sync refresh observation timestamps; race/result/entry counts do not increase. Rounds missing from a refreshed calendar are retained and marked POSTPONED; cancellation is not invented when the source does not state it. Manual CANCELLED status is supported.

## Time and season

SeasonContext returns active_season, latest_completed_race, next_race, last_sync_at, awaiting_results and stale. It chooses the latest available relevant season no later than the current year. Next race is a future scheduled event in that season, never the last race as a fallback. A new season must first be synchronized. Data becomes visibly stale after 24 hours; refresh is explicit.

Historical session availability is conservatively estimated from scheduled session times plus a buffer; it is not an independently recorded publication timestamp. Final corrected historical results and reconstructed participation are a documented residual historical-replay limitation.

## Verified snapshot

See [DATA_QUALITY_REPORT.json](DATA_QUALITY_REPORT.json) for all seasons and per-race result counts, and [SYNC_VERIFICATION.json](SYNC_VERIFICATION.json) for before/after counts. At verification: 275 races, 5,457 results, 5,458 entries; the extra entry can represent participation without a classified result. No duplicate, orphan, missing-reference, impossible-date, future-completed or completed-unverified checks failed.

The synchronized latest race was round 16, **Bahrain Grand Prix in Malaysia, 4 October 2026**, won by **Max Verstappen**. Next was **Singapore, 11 October 2026**. This unusual venue/name is source data, not a manual substitution. The [official results](https://www.formula1.com/en/results/2026/races) and [official calendar](https://www.formula1.com/en/racing/2026) were checked on 8 October. These values belong only in verification documentation; production derives them from data.

Enrichment examples (209 and 11731 are this snapshot's identifiers, not permanent defaults):

```sh
backend-python/.venv/bin/python scripts/enrich_session.py 209 --session R
backend-python/.venv/bin/python scripts/enrich_media.py --session-key 11731
```

FastF1 `--laps` loads lap/tyre summaries; `--telemetry` explicitly permits telemetry download/cache. The SQLite payload stores results/weather and selected lap fields, not a raw telemetry warehouse. Session weather is display enrichment; it is not silently introduced into a historical forecast.
