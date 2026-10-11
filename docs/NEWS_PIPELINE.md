# Formula 1 news pipeline

The application reads public reporting at https://www.formula1.com/en/latest using **Selenium + Chrome**. This is independent of the optional Selenium odds provider. No login, paywall bypass or bookmaker is involved.

## Collection and automation

`NewsScheduler.start()` runs in the Flask entry point (`python backend-python/app.py`), once per process without the Flask reloader. A daemon checks the persisted schedule every 15 seconds and collects every 30 minutes by default. News → Pause automation persists the pause; Refresh news starts an immediate background operation. An OS file lock prevents simultaneous CLI, manual and scheduled crawls on this local deployment.

The app must be running and the machine awake. No operating-system service or external scheduler is installed. WSGI deployments must explicitly start one scheduler or invoke `scripts/sync_news.py` from their own scheduler. `NEWS_AUTO_ENABLED=false` disables the worker. There is no implicit browser/network work when importing configuration or running unit tests.

The crawler checks robots.txt, visits the public latest list, waits for rendered links, limits a cycle to 10 new articles with 2 seconds between visits, and closes Chrome in `finally`. It follows only HTTPS article URLs on `www.formula1.com`. Paid articles marked inaccessible in JSON-LD are skipped. Layout changes, timeouts and unavailable metadata produce a recorded failed or partial run, not invented content. Unique source URLs prevent duplicate insertion. Collected facts are first-observation snapshots: later edits to the same URL are not silently substituted into historical evidence.

Each article stores the source URL/title, source publication timestamp, actual collection timestamp, source hash, a private bounded excerpt (3,200 characters), image URL and generated summary provenance. The API does not expose the raw excerpt. The UI links every short summary and source image back to the original article. No full article is republished. Source media remain remote and require a connection; a clearly labelled illustration is the fallback.

## Local summaries

Ollama runs at `127.0.0.1:11434` with **qwen3:4b-instruct**, a compact quantized model. `NEWS_LANGUAGE=en` preserves the English source language. Romanian generation was rejected after local QA found mistranslations of technical terms and timelines; changing the UI language does not translate these briefs. It uses no OpenAI key, paid API or external inference service. The existing optional OpenAI race-recap feature remains a separate configuration.

The local workspace runtime is under `backend-python/data/runtime/ollama`; models live under `backend-python/data/runtime/ollama-models` and are ignored by version control. `NewsRewriter.ensure_runtime()` can start this already-installed runtime. For a different machine, install Ollama, run `ollama serve`, then:

```sh
backend-python/.venv/bin/python scripts/setup_news_llm.py
backend-python/.venv/bin/python scripts/sync_news.py
```

Generation requests JSON with an original short title and one short summary sentence based only on the official source introduction. The input is deliberately limited to the first factual description: longer multilingual briefs introduced unsupported timelines in local QA. Validation checks structure, bounded length and unsupported numeric tokens; a second LLM pass checks each draft against the source fact. These checks do **not** prove factual accuracy; the UI labels AI summaries and advises checking the source. A failed generation or consistency check stays explicitly pending and is retried in a later cycle. No templated text is misrepresented as LLM output. Numeric prediction signals never come from generated prose.

## Experimental prediction adjustment

The first supported signal is a **confirmed grid/engine penalty**. Extraction requires:

- An explicit penalty in the official source headline, without speculation/negation indicators.
- Exactly one matching current-season driver.
- Exactly one upcoming race, identified in the headline and within 14 days of collection.

General news, sentiment, upgrade speculation and LLM summaries have no numerical effect. These deliberately narrow rules avoid treating every article as evidence of pace. This is an experimental, hand-specified adjustment, **not a trained news model or an evaluated accuracy improvement**. Extend event types only with labelled data, explicit rules and temporal evaluation.

For an eligible driver, multiply its model winner weight by `exp(-0.12)` and normalize across the whole field. Repeated reporting of the same driver/event type is deduplicated; total driver log-weight is capped at ±0.12. Save the original model probability, news-adjusted probability, normalized percentage-point delta, signal IDs, evidence and source URLs. Drivers without direct signals can move slightly because the distribution is renormalized.

Both `published_at` and `observed_at` must be at or before the feature cutoff, the race ID must match, and the signal must not be expired. A story collected after a historical cutoff cannot change that replay. With no eligible signals, probabilities remain exactly equal to the model output. These rules are tested with future publication/collection times, expiry and duplicate articles.

Race winner forecasts consume the adjusted weights; optional market blending follows that step. Championship Monte Carlo uses these race weights for simulated future finishes and therefore expected points/title probabilities. **Official results and current championship points never change.** Base model training and reported walk-forward metrics exclude the experimental news adjustment. Forecast UI tabs expose the base and adjusted components; displayed rank follows the final forecast.

## Operations

- `GET /news`: public brief feed and worker status.
- `GET /news/status`: schedule, model availability, recent durable runs.
- `POST /news/refresh`: queued Selenium + summarization job, HTTP 202.
- `POST /news/automation`: `{ "enabled": true, "interval_minutes": 30 }`; allowed interval 15–1440 minutes.
- `GET /data/jobs/<id>`: manual operation progress (jobs are process-local).

News POST operations use the same local-only/admin-token protection as other administrative endpoints. Durable tables are `news_articles`, `news_signals`, `news_crawl_runs` and `news_automation`, created by additive schema migration 2 after an automatic SQLite backup.

Configuration is in `backend-python/.env.example`. Browser/LLM failures preserve already collected articles and existing model functionality. Runtime and model downloads are installation operations, never repeated for each application launch.

References: [Formula 1](https://www.formula1.com/en/latest), [Qwen3 official model tags](https://ollama.com/library/qwen3/tags), [Ollama](https://github.com/ollama/ollama).

### Reliability and upgrades

Public listing metadata is checked before article navigation: gated/Unlocked, live-coverage and betting promotion cards are excluded. This avoids repeatedly timing out on irrelevant or unavailable pages. Existing articles can still be summarized when the external source is offline. When the configured model or summary language changes, saved articles are rewritten in bounded batches while preserving source observations and prediction-signal timestamps.

Grand Prix grid penalties affect the Grand Prix simulation only. Sprint sessions use the underlying model weights; a Sunday penalty is not silently applied to the independent sprint grid. This is covered by a points-level simulation regression test.

The source consistency review is performed by the same small model and is not a proof of correctness. Additional deterministic checks reject an invented win/podium, engine/gearbox change, pole, crash, retirement or disqualification when the source introduction and headline contain no supporting event category. A strong performance cannot silently become a race win; unspecified upgrades cannot become engine upgrades. Regression tests cover both mistakes found in local generation QA. Rejected briefs remain pending, with the original source link visible.
