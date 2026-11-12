# Trade validation protocol

The November 12, 2026 audit separates useful current-roster modeling from unvalidated next-year prices. The default email shows current gains and future-cost proxies separately. Combined totals and reference scenarios remain in private research details, with an explicit unit/validation warning. There is no validated pick-price ceiling or acceptance probability. Current forecasts, historical synthetic intervals, and future keeper/draft scenarios are different evidence.

## Rule status

Confirmed: two keepers, two rounds earlier, at most two consecutive keeps. Unresolved: original versus latest cost basis, whether cost and keep count transfer with a player, and treatment of a cost earlier than Round 1. Sleeper metadata confirms the keeper count but contains no rule description. Null values remain unresolved; scenario assumptions do not become league facts. These inputs need the manager's confirmation.

## Prospective protocol: trade_fixed_plan_v1

At report preparation, freeze the forecast-selected weekly lineups before and after each displayed player trade or player-for-pick offer. Track both teams. Store the signed player-week changes, scheduled kickoffs, model expected gain, and two baselines: zero gain and the same plans valued using each player's prior four recorded games, adjusted by the already-sealed participation proxy. Four games are required for the recent-form baseline. All history is strictly before the forecast week.

Unchanged players cancel. Identical owner/exposure forecasts are recorded once, so offering a first, second, or third for the same player does not triple the current-season sample. This protocol evaluates current fixed-plan scoring, not next-year pick prices, future managerial decisions, or whether a trade was accepted.

The private archive chooses the earliest retained trade capture per league/origin, including late captures. It never replaces that capture with a better rerun. Actual archive capture time must precede every affected kickoff; missing kickoff evidence or a late capture prevents scoring. No performance scoring is published until all weeks in the original horizon have finalized games and complete team-level statistical coverage. Only observed player scores are populated automatically. Missing player rows remain unresolved; they are not assumed to be zero or DNPs.

Each new private capture creates an immutable scorecard with forecast and outcome archive hashes. Metrics compare model, recent-form, and zero-gain absolute error on exactly the same resolved rows with an available recent-form baseline. Recorded prediction intervals and probabilities also receive descriptive coverage and Brier checks. Reports retain unscored counts and reasons. Offers and horizons overlap; counts are not independent samples. There is no automatic model-promotion decision or interim significance test.

The existing weekly player scorecard and fixed-window workload-momentum study remain in place. This adds a trade-horizon check instead of reusing weekly accuracy as proof that trade prices are correct.

## Evidence boundary and next decision

Mechanics tests can establish that forecasts were frozen, baselines are fair, and outcomes were not fabricated. They cannot establish predictive advantage before the horizons finish. Review prospective errors and unresolved outcomes after settlement; compare against both simple baselines before claiming an edge. Next-year price validation additionally requires settled keeper rules, historical draft/keeper outcomes, and a future roster-utility model on a comparable scale. Do not tune or widen historical intervals based on a live report's eventual outcome.
