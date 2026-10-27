# Waiver research and Tuesday email

The hosted workflow prepares a dedicated waiver email every Tuesday at 10 a.m. America/New_York and a lineup email every Wednesday at the same time. The Wednesday email also includes the latest waiver section. Explicit manual sends choose report_type; default dispatches are email-free. Separate durable delivery keys preserve existing lineup send history and prevent one report from suppressing the other. No claims, bids or drops are submitted.

Show up to five available candidates for QB/RB/WR/TE/K and each league flex category. FLEX uses the imported eligible positions and does not create a second copy of a player in optimization. Rank offense by projected weekly points using the production model; rank kickers with the existing kicking-only baseline. DEF has an alphabetically ordered, explicitly unranked watchlist, without point estimates or FAAB advice. No validated defense model exists yet.

Exclude league-owned IDs (including reserve and taxi lists), owned canonical aliases, inactive/out/doubtful players, unscheduled games, kickoff-locked candidates and unresolved identities from offensive recommendations. Questionable players remain flagged. Being unrostered does not establish immediate claim eligibility; pending claims, league deadlines and drop locks must be checked in Sleeper. Current depth-chart starting roles are not verified. New/sparsely observed players may have weak forecasts; excluded and unresolved availability remains in the private coverage file.

Projected lineup gain compares the optimized current roster with that roster plus one candidate, respecting exact FLEX slots and kickoff locks. It assumes an open roster spot or a safe bench drop. It is not a drop recommendation or rest-of-season valuation. If a complete baseline lineup is unavailable, the gain and related dollar bid are withheld.

FAAB is a transparent spending policy, not a calibrated winning-bid estimate. For FAAB leagues with known integral original budget, used amount and minimum bid, remaining funds equal original budget minus used funds. Recheck commissioner adjustments/trades in Sleeper. Dollar ranges are percentages of the original budget, rounded outward and capped by that remaining balance:

| Projected one-week lineup gain | Budget range |
| --- | --- |
| No gain | 0–1% |
| Positive but below 2 points | 1–3% |
| 2 to below 5 points | 3–7% |
| At least 5 points | 7–15% |

Kickers, injury-designated players and players with fewer than four observations are capped at 1–3%. An eligible modeled kicker covering a rostered kicker with no scheduled game receives a 1–3% coverage guideline; no numerical lineup gain is invented. Unknown budget, insufficient minimum bid, unmodeled defense or unknown roster comparison means no dollar recommendation. Every range is an independent alternative; adding them together may exceed the available budget. These policy boundaries are configurable code, not empirically validated market prices.

Tuesday can still be too early if Monday game statistics have not arrived. Prior-week completeness checks remain mandatory. A failed preparation does not send stale advice. See [Sleeper API](https://docs.sleeper.com/) for read-only league settings, rosters and player data. Reports and full league snapshots remain in the private archive, never public Actions artifacts.

## Add/drop what-if comparisons

The email shows up to ten independent pairs drawn from the displayed offensive waiver candidates and eligible offensive bench players. The private `waiver-add-drop.csv` retains all evaluated feasible pairs. Each pair removes one rostered player, adds one candidate and reoptimizes all offensive slots, including FLEX. The signed change is relative to the optimized original roster; a negative value exposes lost production. Ties sort deterministically by names and IDs.

Assigned starters, reserve/taxi players, unavailable players and kickoff-locked players are protected from removal. Scenarios that cannot fill every offensive slot are omitted. If the baseline cannot be evaluated, comparisons are withheld. K/DEF are outside this comparison because full specialist optimization remains unvalidated.

These are weekly what-if calculations, not recommended drops: future value, keeper value, future availability, undroppable lists, pending claims, positional roster limits and platform drop eligibility are not modeled. The existing FAAB ranges remain add-only guidelines and are not recomputed as pair-specific bids. No lineup or transaction is submitted.

## Next-three-week schedule coverage

Each add/drop pair now shows offensive slots covered before and after the change for the next three regular-season weeks (capped at week 18). Maximum distinct-player matching respects each slot's eligible positions, including FLEX; one player cannot cover two slots. The full matrix is retained in private `waiver-coverage.csv`. The email displays the same weekly-gain ordering as before; coverage does not change bids or predicted points.

This is a schedule-only count assuming non-reserve/non-taxi offensive players are healthy and stay on their current teams. Current injuries and kickoff locks are not projected into future weeks. K/DEF, role changes, trades, future points and keeper value are not modeled. A missing team game means bye or schedule gap, not a verified bye. Entirely missing weeks, duplicate team schedules, unresolved players and unknown teams produce unknown coverage rather than an invented zero. Counts measure capacity, not the quality or certainty of the lineup. Check live eligibility before making claims.
