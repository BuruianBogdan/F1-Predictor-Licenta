# Measured performance and bounds

October 14, 2026 local measurements. These are replay/fixture measurements, not real broadcast latency guarantees.

| Measurement | Result | Evidence |
|---|---|---|
| 20 actual HTTP replay frames | median 46.4 ms, p95 55.6 ms; payload 113114 bytes | LIVE_BROWSER_VERIFICATION.json |
| 30 frames, two concurrent viewer workers with allocation tracing | median 371.6 ms, p95 430.9 ms | LIVE_PERFORMANCE_VERIFICATION.json |
| Serialization, tracing enabled | median 7.2 ms, p95 14.7 ms | LIVE_PERFORMANCE_VERIFICATION.json |
| Lock contention, tracing enabled | wait p95 234.0 ms, held p95 223.1 ms | LIVE_PERFORMANCE_VERIFICATION.json |
| Bounded historical checkpoint | save 160.0 ms, gzip 441277 bytes | LIVE_PERFORMANCE_VERIFICATION.json |
| Synthetic buffer stress | 202500 updates; 2.55s; 7479002 traced peak bytes | LIVE_BUFFER_VERIFICATION.json |
| Genuine FastF1 fallback | 31.2s; 269967 coordinate samples, 292240 car samples | FASTF1_ARCHIVE_VERIFICATION.json |

Allocation tracing adds overhead; the concurrent-worker numbers should not be compared directly to untraced HTTP latency. Trace memory is not total Python/Java/browser RSS. The real separate-window regression and the two-worker contention measurement verify different properties. No running live race was observed, so active source throughput/end-to-end latency remains PENDING_LIVE_SESSION.

The measured local work fits the existing 1.3-second polling interval. The frame lock still serializes some work, and checkpoint copying/compression can briefly block ingestion. These are measured limitations; no unnecessary new SSE pipeline was added.

Bounds: 1,800 coordinates / 500 car samples / 200 observed laps per driver, 4,000 events per endpoint, 4,096 dedup IDs, 60,000 patch leaf fields, nesting 32, 2 MB encoded / 8 MB decoded compressed packets. Checkpoint serialized size is capped at 8 MB; eight files are retained for 30 days. Historical loads are explicit and materially larger than live buffers.

Reproduce with `scripts/verify_live_performance.py`, `scripts/verify_timing_buffers.py`, `scripts/verify_timing_integration.py`, and `scripts/verify_fastf1_archive.py --browser`, using the project virtualenv and running Flask/Spring Boot where needed.
