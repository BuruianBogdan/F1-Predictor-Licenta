> Version 1 historical audit. For the current working tree, winner-confirmation contract and final test results, use [Live Data v2 completion report](LIVE_COMPLETION_REPORT.md).

# Live feed audit — 11 October 2026

Baseline: branch main, commit a52db39; working branch codex/live-feed-integration. The nested F1-Predictor-Licenta checkout is not the running application and is left unchanged. No separate dashboard or OCR is part of this integration.

## Existing flow

`PublicTimingFeed` negotiates the public SignalR Core endpoint, subscribes to twelve channels and checks only SessionInfo.Key. `RaceControlService` shares class-level dictionaries/pools among HTTP callers, merges sparse patches, translates fields into the existing OpenF1-shaped dataset, and returns `TimingTimeline`/`public_frame` snapshots enriched by `RaceStrategyService`. Flask exposes the Race Control catalog/prepare/status/frame routes; Spring proxies JSON; race-control.js polls at about 1.3 seconds and the existing SVG engine interpolates measured locations. Static reference geometry may come from an earlier session in the same meeting. Offline replay and selected-driver telemetry use local gzip archives; no live database module remains after the requested rollback.

`RaceStrategyService` owns the experimental on-track-strategy-v1 model and set-level tyre-wear index. `track_geometry_service` extracts measured start/pit landmarks. `SessionRefreshService` preserves the manual Tools action using the original providers. Jolpica supplies historical identities/results/standings; OfficialWeekendProvider supplies published FP/qualifying/Sprint evidence; OpenF1 and FastF1 supply historical enrichment. None is a substitute for missing live coordinates.

## Findings

- Subscription does not prove receipt: no channel health matrix or event-time freshness exists. CONNECTED currently appears as LIVE even without a fresh matching-session event.
- Identity checks omit season, meeting, session type and schedule. Live and archive datasets share a key and a live prepare can replace a downloaded replay in memory.
- Reconnect is a fixed five-second policy with no observable retry budget or explicit 401/403 handling; negotiation occurs outside the start cleanup guard. The six-hour monitor creates a thread per start and does not provide process shutdown cleanup.
- Live location samples have no retention bound; public event lists and lap history can grow indefinitely. Memory/current-state dictionaries need explicit locks and bounds.
- Compressed samples lack bounded decompression/schema validation. Packet order and event deduplication are not tracked; delayed sparse patches may rewind fields.
- Reception time is used as a substitute for source time for most channels. Unknown source time, keyframes and recovered observations must remain explicitly uncertain/stale.
- Completed lap detection depends on a lap-count increase and current LastLapTime; missing sectors are intentionally unknown, but reconnect history, sector-cycle association, deleted/reinstated laps and TimingStats need more coverage.
- Race control translation drops driver/message identifiers. Pit and tyre-stint histories are incomplete in live frames. Retirement booleans default to false in some presentation fields.
- Speed/gear/pedals are displayed; RPM is not retained in the current six-field compact sample. DRS absence is currently shown as OFF whenever another sample exists.
- No championship projection, diagnostics endpoint, recoverable live checkpoint or in-race historical benchmark exists.
- The forecast is experimental and correctly separate from baseline historical ML accuracy. Its formula will be preserved, with additional data-quality/provenance coverage and chronological evaluation.

## Baseline verification

Executed again: 123 backend tests passed, one existing optional Selenium odds test skipped; nine animation tests passed; 28 Java tests passed. Existing evidence reports were read but are not treated as proof of a newly tested active live session. At audit time the scheduled Singapore GP has ended; a real active-session test is pending.

## Incremental work

1. Instrument the existing public transport, strict identity and per-channel health; expose diagnostics inside the original viewer.
2. Add a lightweight provider contract, timestamp-aware merging and provenance. Keep a single public connection. Use historical providers only for history/static geometry/official baseline, not as live replacements.
3. Bound decoding, sample/event retention, retry budgets and shutdown; persist compact normalized checkpoints and recover them as STALE.
4. Improve lap/sector/pit/stint processing and frame quality without changing the renderer or forecast formula.
5. Add clearly provisional championship projections with season-specific scoring and no official result writes.
6. Add reproducible source probes, multi-cutoff historical model comparisons, browser/replay regression and performance reports. Document source access and incomplete real-live verification.

## Access and reuse

The referenced projects mostly share the same Formula 1 upstream. Their code licences do not authorize subscription data or scraping. No F1 TV credentials, browser tokens, DRM/CAPTCHA bypass or paid live dependency will be introduced. MIT/Apache examples are design references; AGPL f1-dash is read for public architecture/UX only, with no code/assets copied. Primary source comparisons and exact reviewed revisions belong in LIVE_PROVIDER_COMPARISON.md.
