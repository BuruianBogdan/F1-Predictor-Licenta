# Market odds and Selenium

## Working paths

Manual decimal odds are available without external accounts or browser dependencies. POST `/predict/race/{id}/market` accepts `mode`, `odds` and optional batch `captured_at`. Each row has driver_id, odds, optional provider, optional captured_at and source_url. Distinct providers may quote the same driver; duplicate driver rows within one provider are rejected. Values must be finite and greater than one and map to a driver in the target field.

For each provider, convert decimal odds to implied `1/odds`, remove the book margin by normalization, take medians across books and normalize again. Blend with weight MARKET_WEIGHT (default 0.15). For a partial book, its fair distribution is scaled to the model's total mass for quoted drivers; unquoted drivers retain their original probability. Thus an incomplete market never implicitly gives all chance to its few quoted drivers. Podium and points remain the model's unadjusted marginal estimates.

No data means model probabilities remain unchanged. Batch and individual quote timestamps are checked against the prediction cutoff; a later row cannot be disguised by an earlier batch timestamp. Manual historical timestamps are user assertions, not independently authenticated archival evidence. Snapshots are stored with provenance and linked to prediction history.

The prediction UI takes manual rows. Selenium snapshots can be inspected using GET `/odds/{id}` and passed to the market endpoint with their original timestamps. The UI does not silently substitute cached bookmaker data for manually supplied rows.

## Optional Selenium

Set SELENIUM_ENABLED=true and ODDS_SOURCES to a JSON list in `.env`. A source has name, url, row_selector, name_selector, odds_selector and optional aliases mapping external names to local driver IDs. Configure only a permitted public decimal-odds page for the intended race. The operator must verify the page refers to that race: arbitrary page selectors cannot establish event identity automatically.

The shared page object uses Chrome, explicit waits, Unicode-insensitive driver mapping, comma/period decimal parsing, a configurable timeout, source URL and capture timestamp. `driver.quit()` runs in a finally block on success or failure. There is no account login, CAPTCHA bypass, stealth mode or automatic bet placement. Refresh is explicit via POST `/odds/refresh/{id}`, isolated per provider and cached for ODDS_REFRESH_MINUTES (10 by default).

Real-provider status: **none configured; none verified**. Local test fixture `backend-python/tests/fixtures/odds_page.html` was tested with real headless Chrome on 2026-10-08; parsing and cleanup tests passed. The equal-odds demo endpoint is labelled synthetic and is not a bookmaker feed.

```sh
RUN_SELENIUM=1 backend-python/.venv/bin/python -m pytest backend-python/tests/test_odds_parser.py -q
```

There is no archived historical market dataset, so ML+market walk-forward metrics and market profitability are unavailable. Functional normalization tests are not evidence of predictive gain.
