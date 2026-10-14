# Continuous replay, car condition and on-track strategy

## Fixed replay behavior

Singapore Sprint Qualifying has multiple SESSION FINISHED events. These end SQ1 / SQ2 as well as SQ3. The earlier viewer treated every one as the overall end, stopped playback on its next frame request, and exposed the final SQ3 classification too early. The timeline now returns BREAK for intermediate finishes, with no final winner or classification. Only the last terminal finish returns FINISHED. The live connection supervisor also does not shut down after an intermediate qualifying finish; a restart clears the pending end state.

The earlier map fetched only twelve seconds of upcoming coordinates every ~two wall-clock seconds. At 10× and 30×, the replay clock outran that window and the cars appeared to freeze. The lookahead is now `clamp(7 × speed + 15, 30, 240)` seconds. Windows include six seconds behind the current timestamp, and the Java proxy / backend bound the requested size. These are measured archived samples, not fabricated vehicle positions.

`race-control-engine.js` holds a frame-rate independent clock. Request completions, driver changes and keyboard speed changes do not reset its elapsed time. Superseded frame requests are aborted and discarded; an old request cannot clear the busy flag of a newer one. The live clock does not rewind when response latency varies. The separate window preserves replay time, pause state, speed and selected driver.

Replay URLs can now target the actual late portion of a delayed GP even after its nominal scheduled end. The first loaded frame supplies actual timeline bounds; the URL is not prematurely clamped to the old published schedule.

## More readable measured map

Bounded monotone cubic interpolation gives smooth positions between samples without overshooting the measured segment bounds. Long sampling gaps are explicitly shown as delayed positions; stationary measured cars are not made to move. Dots and labels are independent layers. Each name stays centred close above its own dot, with only an 8-pixel forward adjustment from the measured direction of travel. Overlap is intentional; neighbours, timing rank and selection priority never displace a label. A short connector identifies the matching dot, and the readable chip supports mouse and keyboard selection. Selected drivers have a direction marker and a short measured trail. The map adds a road surface, phase / freshness HUD and sector reference markers from the measured reference lap.

The underlying public locations remain approximate. Wheel-to-wheel lateral placement cannot be recovered from these samples. This change improves playback and presentation; it does not claim higher physical accuracy than the source provides.

## Tyre-set estimate

The public [OpenF1 stint endpoint](https://openf1.org/docs/) supplies compound, stint boundaries and tyre age, not individual wheel wear. The public car data channels also do not provide four wheel-wear percentages or component damage sensors.

Each driver gets a **model index for their tyre set**, shown on all four tyres. Missing age / compound stays grey and unavailable. Different front / rear percentages are not invented. The diagram labels every value as estimated, shows the set-level limitation and displays grey bodywork as unknown condition.

Reference life assumptions at a 5 km lap:

| Compound | Reference laps | Default pace slope (s/lap) |
| --- | ---: | ---: |
| Soft | 28 | 0.055 |
| Medium | 42 | 0.035 |
| Hard | 55 | 0.020 |
| Intermediate | 32 | 0.040 |
| Wet | 38 | 0.045 |

These are tunable heuristic references, **not Pirelli measurements or guaranteed tyre lifetimes**. Within the current stint, the median pairwise pace slope is used when at least four clean completed laps exist, bounded to 0–0.15 s/lap. Negative fuel-related slopes do not imply negative wear. Deleted, pit / out, neutralised and markedly slow laps are excluded. Known tyre age is attached to each completed lap so a new set does not inherit the old set’s wear when estimating baseline pace.

```
heat_factor = clamp(1 + (track_temperature - 35) × 0.004, 0.90, 1.15)
trend_factor = clamp(1 + max(0, observed_slope - default_slope) × 2.5, 1, 1.25)
adjusted_life = reference_life × 5 / circuit_length_km / heat_factor / trend_factor
wear_index = clamp(100 × (tyre_age_laps / adjusted_life)^1.08, 0, 100)
```

Colour interpolates green → yellow → orange → red at index thresholds 0 / 35 / 60 / 85. This is an approximate wear indicator for comparison, not a claim that the tyre is physically consumed by that percentage. Unknown underlying compounds, fuel, pressure, traffic, driving style and surface conditions limit it.

## Incident / body condition

Race Control messages are timestamp-filtered and associated with the named drivers. Collision, contact, crash and explicit damage reports enter the incident feed and selected driver panel. A collision report adds a red **impact alert** to the body diagram and map dot; it does not set any unknown component’s state to damaged. A component becomes red only if a message explicitly names its damage. Explicit replacement / repair reports can clear that component’s damage state. False starts, track limits and ordinary investigations are not treated as body damage. Confirmed retirement is separate from a generic incident report.

Incidents appear when the source reports them, which can be later than the physical event. There is no severity percentage, exact impact-location reconstruction or medical inference. The illustration’s red centre is an alert, not a sensor reading of body integrity.

## In-race winner estimate

Race Control now has **The race ahead**, recalculated with each timing frame. The Predictions page links to it through **Race strategy and in-session forecast**. Grand Prix / Sprint forecasts use the current gaps, observed clean pace, tyre-set age / compound, neutralisation state and estimated future stops. Practice / qualifying show tyre estimates and timing, without a race-winning forecast.

The strategy model is independent of the existing pre-event calibrated classifier. It is named `on-track-strategy-v1`, marked experimental, and **has not been calibrated or backtested**. The historical classifier’s published accuracy must not be attributed to this model.

- Pace is estimated from completed clean laps, corrected using the tyre age of those laps. A field pace fallback is used only when other drivers have real usable laps.
- Planned total laps come from public LapCount or a known Race Control announcement. Otherwise the model explicitly assumes nominal distance / reference circuit length. Future final classification / final completed laps are not used to infer planned distance.
- Current gap plus projected remaining lap pace forms an estimated finish cost. Increasing tyre age increases modeled degradation; a set replacement resets modeled age. A heuristic stop is projected near 82% of reference tyre life if sufficient distance remains.
- Green-flag net pit loss is the median excess of completed representative pit laps when three usable samples exist; otherwise the model explicitly assumes 24 seconds. Future actual stop duration is not used. For a car already in the lane, remaining loss is modeled from observed entry time and the estimated loss.
- Current pit-loss factors are 1.00 green, 0.90 **local yellow**, 0.65 VSC and 0.50 Safety Car. These are assumptions, not universal facts about a circuit. A local yellow does not guarantee the same opportunity as SC / VSC. Future stops do not assume that the current neutralisation continues indefinitely.
- Missing tyre age is not treated as a fresh set: the field median is assumed, or 15 laps if all ages are missing, with wider uncertainty. The tyre diagram itself remains unknown.
- 1,800 seeded simulations add finish-time uncertainty for remaining distance, planned stops and missing observations. Confirmed retired / DNS / DSQ drivers are excluded. Model coverage and missing data remain visible. A completed session shows the confirmed result, clearly labeled as a result.
- A selected-driver battle card compares observed / estimated pace and the current gap to the car ahead. Catch-up laps are an estimate, not a guaranteed pass. Future accidents, defensive driving, fuel and restart choices remain uncertain.

All model inputs are filtered at the replay / live frame cutoff. Seeking backwards reconstructs tyre / incident / forecast state at that point. The existing pre-event history, model artifacts, source result tables and baseline metrics are not modified by these calculations.

## Verification

```
backend-python/.venv/bin/python -m pytest backend-python/tests -q
node --test scripts/tests/race-control-engine.test.js
mvn -f frontend-java/frontend-java/pom.xml test package
backend-python/.venv/bin/python scripts/verify_race_control_strategy.py
backend-python/.venv/bin/python scripts/verify_race_control.py
```

`RACE_STRATEGY_VERIFICATION.json` records the real SQ intermission regression, continuous 30× playback, hundreds of measured movement updates, the actual GP collision report / red alert, tyre estimate and running forecast, five viewport widths, and zero relevant browser errors. Unit tests cover new-tyre advantage, missing measurements, yellow versus SC, future-data exclusion, false incident classification and intermediate session endings. The original viewer verifier still covers the independent popup, live start gating, sectors, flags, telemetry and confirmed winner transitions.

This work does not alter the earlier limitation of the free live source. Live position / car channels can be missing or the public connection unavailable. Complete moving-map functionality is verified with real archived replay; no paid source or access workaround is used.
# October 11 evaluation and quality additions

The strategy formula remains `on-track-strategy-v1`. Live input channel quality, missing fields and clean-pace coverage are now exposed; waiting/stale live inputs pause estimates. [LIVE_BACKTESTING.md](LIVE_BACKTESTING.md) and [LIVE_BACKTEST_RESULTS.json](LIVE_BACKTEST_RESULTS.json) contain a small chronological four-session evaluation at five cutoffs. This is descriptive validation, not calibration, and the strategy underperformed the leader baseline. Older statements that no backtest existed refer to the original implementation date.
