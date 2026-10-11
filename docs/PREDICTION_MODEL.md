# Prediction methodology

## Dataset and cutoffs

A dataset row is `(driver, target race)`. Entrants are stored separately from outcome labels. Numeric features use an explicit allowlist of 32 fields. Driver inputs include starts, prior season points/rank, rolling position/points windows of 3/5/10 races, recent wins/podiums, reliability, trends and prior circuit record. Constructor inputs include prior points/rank, rolling team form, podium/DNF rates and momentum. Context includes round, regulation era and historic circuit DNF rate. Qualifying is enabled only in POST_QUALIFYING. Grid placeholders remain unknown for factual inference; target result grid is forbidden.

PRE_WEEKEND cutoff is the earlier of now and weekend start (race start minus two days when unavailable). POST_QUALIFYING cutoff is the earlier of now and race start minus one second; qualifying must be available before it. Earlier race outcomes also require a six-hour finalization buffer. POST_PRACTICE is accepted as a labelled fallback mode but has no trained practice model or measured practice features.

The feature builder filters by date/time, not database ID, excludes the target's results, and applies timestamps to sprint/qualifying records. Labels are attached only after features are built. Artifacts are eligible only if their training cutoff is strictly earlier than the feature cutoff. Reconstructed replay runs are labelled, never presented as genuinely recorded pre-race predictions. Historical final corrections and reconstructed rosters remain limitations; preventing target-outcome leakage does not create an as-published archive.

## Estimators and validation

HeuristicBaselineModel is an explicitly named weighted softmax baseline. RaceMLModel uses scaled logistic regression (`C=0.2`) for winner, podium and top-ten labels. HistGradientBoosting is benchmarked with fixed settings. Logistic was selected in advance for simplicity; test-set comparisons do not automatically choose the best candidate.

Each classifier is sigmoid-calibrated from logits using a later, disjoint season. Winner probabilities are normalized over the field and podium/points marginals are made monotonic. Evaluation uses these final outputs. The ranking sorts winner probability; it is not a dedicated finishing-position regression model.

For holdout 2022: fit 2014–2020, calibrate 2021, test 2022. Advance this split annually through test 2025. Production fits 2014–2024 and calibrates on 2025. No random split is used. See MODEL_CARD.md and evaluation JSON for actual measurements.

All probabilities are fractions in `[0,1]`; multiply by 100 for UI display. Winner sums to one. Podium and points marginals need not sum exactly to three and ten. `points_probability` currently means **top-ten finish**, not every possible points-award rule. `win_percentage` is an explicit compatibility/display field. Factors are observed values, not SHAP attribution.

## Championship

Starting from season-specific official standings, simulate remaining scheduled races and future sprints using fixed current form, race weights, Plackett–Luce sampling and independent reliability draws. Full race points and sprint points are allocated. Race finishing-place countback resolves points ties; truly unresolved champion ties share probability. Default 5,000 simulations and seed 42 make runs reproducible.

Limitations: DNF receives no points even if classified; shortened events are not modeled; sprint strength equals race strength; future replacements, correlated incidents, upgrades and strategy are not forecast. No fastest-lap bonus is modeled for future historical-rule hypotheticals. Requesting a completed old season returns its known final standings rather than a past championship forecast.

## What-if and regulations

Scenarios copy feature rows, leaving production facts unchanged. Pace changes rolling driver/team finish features, scaled by budget_cap_upgrade_weight. Reliability and DNF deltas are percentage-point interventions scaled by reliability_weight. A hypothetical grid position multiplies winner weight by `exp(0.08 * (field_midpoint - grid))`, then the field is normalized. This is a declared sensitivity assumption, not a learned grid effect.

Regulation uncertainty mixes the distribution towards uniform: `0.1*(aero_rule_change_weight+safety_car_randomness)`, plus `0.1*sprint_impact_weight` for a sprint weekend, plus wet_race_uncertainty when wet is selected, capped at 0.8. These are scenario assumptions, not estimates of causal regulation effects. The baseline uses unchanged production prediction; the scenario includes these interventions, and the UI shows the probability difference.
