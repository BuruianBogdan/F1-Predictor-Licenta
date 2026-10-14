# Testing

```sh
backend-python/.venv/bin/python -m pytest backend-python/tests -q
mvn -f frontend-java/frontend-java/pom.xml clean test package
node --test scripts/tests/race-control-engine.test.js
```

The preserved application includes Race Control, track geometry, replay, strategy estimates, published weekend/Sprint predictions, news, CRUD and reports. Session refresh tests cover forced schedule acquisition, all public sessions, partial source failures, job deduplication and persistent metadata.
# Race Control integration verification

New offline cases are in `tests/test_timing_integration.py`: source identity, UTC/future ordering, null/false/tombstones/sparse slots, bounded decompression, RPM, missing channels, retry access denial, archive isolation, STALE checkpoint recovery, weather ranges and provisional scoring. Run the original suites plus `scripts/verify_timing_integration.py`, `scripts/verify_timing_buffers.py`, `scripts/backtest_race_strategy.py` and `scripts/verify_live_sources.py`. Real live access is not inferred from these fixture/replay tests. Current reports and limitations are linked in [LIVE_INTEGRATION_REPORT.md](LIVE_INTEGRATION_REPORT.md).
