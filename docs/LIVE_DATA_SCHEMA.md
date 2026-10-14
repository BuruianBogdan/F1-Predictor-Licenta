# Timing observation schema and provenance

No SQL migration is introduced. Existing frame fields remain compatible; new fields are optional additions.

| Field / structure | Meaning |
|---|---|
| `meta.session_key`, `meeting_key`, `year`, session name/type/start | Validated context; driver numbers are local to this roster/session |
| `at` / `diagnostics.cutoff_utc` | Explicit frame cutoff, in Unix UTC seconds / ISO UTC |
| `rows[].provenance[field]` | Provider ID, session key, source observation UTC, receipt UTC, age and OBSERVED / UNDATED_SNAPSHOT validity |
| `rows[].timing_state` | Channel quality; a retained unchanged value is not a newly measured sample |
| `rows[].pit_stops`, `pit_events`, `pit_stops_source` | Published count, or entries actually observed since connection; unavailable is null |
| `locations[number][]` | `[UTC, X, Y]`, real coordinates only |
| `telemetry[]` | `[UTC, speed_kmh, gear, throttle_percent, brake_percent, raw_drs_code, rpm]`; first six columns retain compatibility; absent channels are null |
| `weather` | Timestamped values, explicit wind unit and per-field provenance for live observations |
| `public_laps` | Observed completed laps with UTC start/end; missing sectors stay null; deleted/reinstated times processed at announcement cutoff |
| `TimingStats` aggregates | Published personal/session sector bests, not invented lap-history records |
| `championship_projection` | PROVISIONAL / PARTIAL / STALE_INPUTS / UNVERIFIED_STOPPAGE_RULES, read-only baseline and session points |
| `diagnostics.channels` | Requested/received packet counters, valid/rejected/duplicate counts, source/receipt UTC, source age, measured receipt-minus-source latency and reason |

Sparse array slots retain their indices: an update for S3 cannot shift into S1. Omitted fields are unchanged; null is explicit; false remains false; `_deleted` lists/tombstones clear fields. Deduplication hashes session/topic/source-time/content into a bounded 4,096-event window. Leaf timestamps prevent an older or undated snapshot from replacing a newer observed value. An older patch may fill a distinct previously absent leaf.

Arrival time never substitutes for unknown source time. Offset-free dates are rejected unless the provider field/envelope explicitly declares UTC (for example RaceControlMessages.Utc); those fields are normalized with an explicit UTC offset; SessionInfo local start is converted with its explicitly provided GMT offset. Future-dated packets and invalid drivers/numeric ranges are rejected. Undated subscription values may be displayed as uncertain current snapshots, but cannot establish LIVE freshness or create past laps.

Compressed data is validated base64 and raw-deflate/zlib JSON, with 2 MB encoded and 8 MB decoded limits, complete-stream checks and rejection of trailing streams. Patch nesting and indexed sizes are bounded. Race-control driver/message identifiers are preserved.

Source age for sparse state means “time since this field changed/was observed”, not proof that a stable compound changed every heartbeat. Coordinates and car samples are time series; the renderer freezes unavailable/stale samples instead of extrapolating a fictional lap. The broadcast's video delay is not measured.

## Live Data v2 completion
Frames include `result_confirmation`: status, leader, winner_confirmed, session_finished, result_published, result_verified, source, observed_at and verification_scope. `LIVE_LEADER` / `PROVISIONAL_P1` / `SESSION_FINISHED` describe timing; `RESULT_PUBLISHED` means known published classification but not yet mapped uniquely; `RESULT_VERIFIED` is a verified non-race result; `OFFICIAL_WINNER_CONFIRMED` is a uniquely mapped published race winner. `SESSION_CANCELLED` never has a winner.

`OBSERVED_AT_CUTOFF` uses an eligible version. `HISTORICAL_LATEST` is an explicitly labelled final replay outcome view; it is never the championship baseline or an earlier prediction feature. Corrections update the final transition when the confirmed driver changes.

Projection driver rows include team and position_change. `UNVERIFIED_BASELINE` withholds official/projected totals when legacy results lack observation time. Missing driver mapping or uncertain retirement classification withholds aggregate totals. Scheduled laps and required green laps must be observed for STOPPED_NOW; 2022 additionally requires a verified inability to resume. Older interrupted-race rules and seasons outside 2019–2026 remain unverified instead of silently using 2026 rules.
