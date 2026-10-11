# Update all sessions

Tools → **Update all sessions** remains available in the original application. It now uses `SessionRefreshService`, the existing `RaceControlService` and `WeekendService`, without a data platform, OCR, SSE collector, subscription adapter or new database tables.

The button starts one explicit background admin job. Repeated clicks while it runs return the same job. The dialog shows schedule acquisition, published-result/prediction checks, progress for each archive and source warnings. It downloads every missing session that the source already exposes as a public replay. Ready replays open the original `/race-control/{race_id}` viewer. Upcoming/live-window sessions remain visible but are not represented as available archive data.

The current weekend is selected from pending Grand Prix results or the next scheduled race, rather than a hardcoded race ID. Verified schedule metadata is retained on disk so temporary source failure does not erase already known sessions. Source errors result in PARTIAL, while cached replays and previous classifications are retained. Before the Grand Prix, the existing published-weekend workflow recalculates its forecasts; after the race, published-result sync is used only when the Grand Prix archive is available.

After a completed update, closing the dialog refreshes ordinary application pages. The Race Control viewer is preserved while running. This manual action does not install an automatic polling worker or enable another live source.

Backend: GET/POST `/race-control/sessions/refresh`; same-origin frontend bridge: GET/POST `/race-control/api/sessions/refresh`. POST returns HTTP 202. Local/admin-token and same-origin protections remain. There are no former data-platform routes or screen-reader endpoints.

Verification: `tests/test_session_refresh.py`, Java rendering/proxy tests and `SESSION_REFRESH_VERIFICATION.json`. The eight backend regressions cover forced schedule refresh, every public session, partial failures, acquisition locking, duplicate jobs, verified catalog restoration, empty sources and just-started Grand Prix selection.
