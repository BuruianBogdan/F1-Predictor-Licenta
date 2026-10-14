# In-race evaluation methodology (v2)

`python scripts/backtest_race_strategy.py` uses the existing strategy without training or tuning. It evaluates four archived sessions at 10%, 25%, 50%, 75% and 90% of actual session elapsed time, filtering timing/tyres/control messages at each cutoff. The final classification is only the evaluation label. Complete probability distributions and cutoffs are saved in [evaluation/LIVE_BACKTEST_RESULTS.json](evaluation/LIVE_BACKTEST_RESULTS.json).

A pre-race favorite is used only if a saved non-replay PredictionRun was created before session start, with earlier verified training/feature cutoffs. None was available in this dataset; the old retrospectively reconstructed model baseline has been removed.

| Method | Cutoffs | Top-1 | Top-3 | Brier | Log loss | ECE | Race coverage |
|---|---:|---:|---:|---:|---:|---:|---:|
| current_leader | 20 | 0.900 | 0.900 | 0.200 | 2.763 | 0.100 | 100% |
| observed_pace | 15 | 0.667 | 0.667 | 0.667 | 9.210 | 0.333 | 75% |
| strategy_v1 | 13 | 0.385 | 0.462 | 0.752 | 3.739 | 0.253 | 75% |

Strategy supplied 13/20 cutoff forecasts across 3/4 sessions; its Top-1 was 38.5% versus the current-leader baseline 90%. This small descriptive sample does not support a calibrated or superior live model. L1 changes and cutoff coverage are in JSON. One-hot baselines only offer a single nonzero pick, so Top-3 equals Top-1. Log loss clips zero winner probability at 1e-12. Race coverage means at least one sufficient cutoff, not complete coverage at every cutoff.

Historical files can contain retrospective corrections and unknown publication delays; event-time reconstruction is not a contemporaneous streaming log. Four sessions and correlated within-session samples are insufficient for broad generalization or ECE calibration claims. No future actual pit duration, future flags or final classification enters forecasts. Coordinate-free evaluation caches are separate from UI replay archives. Evaluation is INCOMPLETE for broad calibration and the saved pre-race comparison.
