# UI and News delivery — October 2026

Implemented on top of the existing research application, preserving its original repositories, CRUD APIs, datasets and trained models.

- Added official high-resolution portraits for the 22 current drivers, a portrait grid, and an original generated calendar backdrop.
- Added attributed SVG circuit outlines for all 33 stored circuits: winner panel, race detail, upcoming card and calendar.
- Replaced the all-seasons table with a season selector, ordered future races, recent completed races and explicitly separated unverified/cancelled rounds.
- Added Formula1.com news collection using real Selenium, a durable 30-minute worker schedule, pause/refresh controls, local LLM summaries and source links.
- Added an experimental, bounded penalty signal to race forecasts and Monte Carlo expected points; no changes to official standings or reported ML evaluation metrics.
- Added migration 2 with backup, provenance timestamps, deduplication and replay cutoff protection.
- Added CSS/JS content hashes so browser caches cannot retain outdated News layout styles after a page reload. News images are explicitly constrained to their frames.
- Added desktop/tablet/mobile layout checks at 320, 390, 768, 1440 and 1920 px, plus server-side template and news pipeline regression tests.

Main implementation: `backend-python/{api/news_routes.py,data_sources/news_provider.py,models/news.py,services/news_service.py,services/news_rewriter.py,services/news_impact_service.py,services/circuit_service.py}`; `frontend-java/frontend-java/src/main/{java/com/f1predictor/frontendjava/controller/NewsController.java,resources/templates/news.html,resources/templates/races.html,resources/templates/fragments/circuit.html,resources/templates/fragments/news.html}`. Existing dashboard, race, driver and prediction templates/services are extended in place.

Details and reproducibility: [NEWS_PIPELINE.md](NEWS_PIPELINE.md), [UI_ASSETS.md](UI_ASSETS.md), [UI_LAYOUT_VERIFICATION.json](UI_LAYOUT_VERIFICATION.json), [E2E_VERIFICATION.json](E2E_VERIFICATION.json), [TEST_VERIFICATION.json](TEST_VERIFICATION.json).

Final local verification: 61 backend tests passed (one opt-in browser fixture skipped; previously verified separately), 14 Java tests passed, 30 responsive page/width checks passed, 19 live frontend GET pages plus six POST flows verified. Automatic News run completed successfully with 12 English briefs and no pending summaries. Source/report: NEWS_VERIFICATION.json. Romanian LLM generation was evaluated and rejected for factual/terminology errors; the delivered feed uses English source-language briefs with automatic consistency checks.

## Published weekend updates and Sprint — October 9

Predictions now includes Update weekend, scheduled session cards with official leaders/times, a Grand Prix/Sprint target selector, current-weekend probabilities, expected points, per-driver evidence and comparison with the last saved update. The asynchronous update reloads the result automatically. The GP dashboard favourite uses the last saved weekend forecast. Source observations are versioned; actual Sprint points enter standings once and feed championship Monte Carlo. Technical method and limitations: [LIVE_WEEKEND.md](LIVE_WEEKEND.md). Verification: [LIVE_WEEKEND_VERIFICATION.json](LIVE_WEEKEND_VERIFICATION.json).
