# Known limitations

The original Race Control viewer depends on public timing availability. Complete archived sessions use measured data; live coordinates and car channels may be missing from the public feed. See RACE_CONTROL.md and RACE_STRATEGY.md.

Tyre wear and in-race forecasts are labelled estimates; unreported damage is unknown. Pre-race and Sprint overlays use published session observations and remain experimental. See LIVE_WEEKEND.md and MODEL_CARD.md.

Tools → Update all sessions checks the current weekend manually and downloads public archives using the original Race Control service. Future or source-protected sessions are not fabricated. Source warnings appear in the update dialog.
# Current feed integration limitations

The original Race Control is instrumented with channel/source quality and a historical FastF1 fallback. No live coordinate/car channel was received in the post-session probe; validation during a running session is pending. The experimental strategy now has a small descriptive benchmark, not calibrated live accuracy. See [LIVE_LIMITATIONS.md](LIVE_LIMITATIONS.md) and [LIVE_BACKTESTING.md](LIVE_BACKTESTING.md) for the current evidence.
