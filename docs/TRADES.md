# In-season trade calculator and digest

The hosted trade digest runs Tuesday at 10 a.m. America/New_York alongside the waiver email. Each report has its own delivery key. Jobs run sequentially so private archive and delivery-ledger writes do not race. Merge-triggered lineup/trade runs prepare reports without sending; manual dispatch offers `trades` and a separate send switch. Existing Gmail credentials and email activation apply.

## What the values mean

The calculator optimizes both teams' offensive starters before and after each proposal, using imported slot eligibility including FLEX. A value of +12 means twelve additional projected starting-lineup points over the displayed weeks, not twelve points per week or a player market price. The digest scans one-for-one swaps, keeps positive gains for both sides at one-decimal display precision, sorts by your gain, and shows at most one proposal per partner. That rounding filter is not a statistical-significance test. Weekly tables expose negative weeks and bye coverage behind the total.

One pregame weekly model is fit on prior weeks only. Future fixtures are predicted independently with current historical features; predicted outcomes never become training data. The default horizon is four weeks, capped at week 17. If any game in the current week has started, the comparison starts next week. The league's trade deadline is respected; after the email cutoff, trade preparation and sending return `trade_suppressed` without emailing a closed-window report. Trade-review delays are not simulated.

These are current-role scenarios, not a validated rest-of-season valuation model. Opponent and bye schedules vary across weeks; future roles and injury recovery do not. Active players with injury designations are excluded from trade candidates. Currently unavailable players stay unavailable, reserve/taxi players are excluded, and players with fewer than four historical games have unknown forecasts. An unknown player-week blocks that team's comparison rather than being treated as zero. Partial scoring coverage is disclosed in the email. Defense, kickers, keeper value, bench insurance, playoff qualification, and acceptance probabilities are not valued.

## Evaluate a custom proposal

Prepare a private digest (requires the existing hosted league environment variables):

```powershell
python -m fantasyfootball.reports.hosted prepare --output work/trade-digest --report-type trades
```

Inspect `work/trade-digest/plan/trade-rosters.csv` for canonical player IDs and roster IDs. The calculator supports multiple players on either side:

```powershell
python -m fantasyfootball.trading --plan work/trade-digest/plan --partner 2 --give player-id-a player-id-b --receive player-id-c --partner-drop player-id-d --output work/trade-comparison.json
```

A proposal cannot increase either team's active offensive roster size. Supply required drops explicitly; open roster slots are conservatively not assumed. Ownership, duplicate IDs, eligibility, and overlapping trade/drop lists are validated. Output contains per-week points and filled-slot counts for both teams before and after, aggregate gains, and the snapshot timestamp. Refresh the digest before making a decision; the calculator does not refresh saved evidence or submit offers.

Trade rosters, projections, and the report JSON join the existing private evidence archive. They are never uploaded as public Actions artifacts. HTML uses UTF-8, semantic tables, explicit point units, and text equivalents; it does not invent confidence bars for an uncalibrated multi-week comparison.

## Validation

Tests cover surplus versus FLEX value, byes, unknown forecasts, negative projections, ownership, explicit drops, injury exclusions, training cutoffs, one fit across future weeks, started-week rollover, deadline closure, HTML escaping, and separate exactly-once trade delivery. A saved historical league snapshot is used for an offline integration check; it is not current trade advice. Hosted execution and inbox delivery require merge and a subsequent run.

## Next-year draft picks

The trade digest fetches the league's draft configuration and traded-pick ledger from Sleeper. Each pick has an immutable `year:round:original-roster` ID and a separate current owner. Untouched picks belong to their original roster; transferred picks follow the ledger's current owner. Next-year configuration is preferred. If absent, the last completed draft supplies a **provisional** round count, visibly separated from the league's potentially conflicting `draft_rounds` setting. Auction formats and ambiguous configurations do not generate numbered pick assets.

`trade-picks.json` preserves ownership, fetch time, configuration source, and the full possible overall-pick range within each round. These ranges are not confidence intervals or predicted finishing positions. Keeper costs, traded future picks, and a different next-year player pool can materially change value; the current model does not claim a fair price for picks.

Include picks in either side of a custom proposal:

```powershell
python -m fantasyfootball.trading --plan work/trade-digest/plan --partner 2 --give-picks 2027:1:3 --receive player-id-c --drop player-id-a --output work/pick-trade.json
```

Pick ownership and duplicates are checked. Player-for-pick and pick-only trades are supported. Picks do not consume roster slots, but receiving an extra player requires an explicit drop. Results report the current-season lineup-point change and keep future pick value **null/unpriced**, never zero. Pick-backed offers are not automatically ranked as fair deals until draft/keeper rules and a suitable future valuation model are available. No offers are submitted.

Source: [Sleeper API draft and traded-pick documentation](https://docs.sleeper.com/).

Confirmed league/year round counts live in `config/trade-rules.json`, selected by the hosted workflow's `FF_TRADE_RULES` path. The 2027 round count for this league is user-confirmed as 15; keeper rules are still unspecified. A later configured draft that conflicts with this count fails explicitly. Local preparation can set `$env:FF_TRADE_RULES='config/trade-rules.json'` to use the same confirmation. Confirmations never carry into a different league or year automatically.

## Deadline and delivery guard

The email spells out the league deadline week, date of its final scheduled game, kickoff in Eastern time, and the trade review period. Sleeper closes trading when that final game **ends**, not when the week's first game starts; accepted trades may process afterward. The calculator can still evaluate next-week benefits after Thursday kickoff in the deadline week.

Because the final whistle has no fixed timestamp, the email pipeline conservatively stops at the **kickoff of the deadline week's final game**. This is an email cutoff, not a claim that league trading has closed. Tuesday preparation checks current league rules before modeling; sending separately reloads league rules and schedule before touching the delivery ledger or SMTP. Unknown deadline data fails closed. Suppressed reports skip private archival and sending cleanly. No trade email is sent during or after the final deadline game. Waiver and lineup schedules are unchanged.

## Repricing draft-capital scenarios

Each digest refreshes standings and pick ownership. For `reverse_standings` rules, the current-season finish scenario ranks original teams by winning percentage (ties count half), then points scored; tied teams share possible slots. Even snake rounds reverse the order. A traded pick follows its original team's performance, not its current owner's performance. For `random`, standings do not affect the main estimate. With `unknown`, all slots retain equal weight and a separate reverse-standings column is explicitly conditional. These scenarios do not model playoffs, a lottery, commissioner discretion, or final-position probabilities. Full-round bounds remain available and never masquerade as confidence intervals.

The optional comparison index is `100 / sqrt(overall_pick)`, averaged over the scenario's slots. This is an explicit **heuristic rank index**, not an empirical valuation curve, fantasy-point forecast, statistical significance result, or fair trade price. Its curve has not been backtested. Net pick index is reported separately from the current-season lineup gain; future monetary/market value remains null. Do not sum those units. The email shows first-three-round scenarios; all rounds are stored for the calculator and private archive.

Set the year-specific `draft_order_rule` in `config/trade-rules.json` only after confirming league rules. The current league is marked `unknown` pending that confirmation. Keeper rules and costs are still needed to develop a defensible future-value model; a changing rank index alone does not establish that an offer is fair.

Deadline source: [Sleeper trade deadline and review-period rules](https://support.sleeper.com/en/articles/2435411-when-is-my-trade-deadline).

## Roster needs before point totals

The season-specific `priority_positions` setting in `config/trade-rules.json` records manager priorities; this league's 2026 priority is **RB**. The digest must acquire an RB and improve projected RB starting points. It cannot reduce RB roster count, worsen RB starting-point totals in any modeled week, weaken the top starters-plus-one-backup point total, or reduce available starter/backup coverage below its existing level (capped at required starters plus one). This is a conservative constraint on forecast scenarios, not an injury probability model.

Both teams must still gain projected lineup points, and neither may acquire a new weekly lineup vacancy. A gain confined to a single week with an existing vacancy is treated as a waiver/bye-week patch and excluded from automatic trade suggestions. Recommendations sort by priority-position improvement before total lineup gain. If nothing passes, the email says so rather than substituting QB/TE offers. Other positions may still lose depth in an RB-upgrade trade; only the declared priority receives the stronger backup-quality protection.

The custom calculator still evaluates proposals that violate these preferences, but returns `recommendation.eligible=false` with reasons and weekly positional before/after metrics. It does not mistake a mathematical lineup gain for a recommended trade. Priorities apply only to the configured season and do not silently carry into next year's league.
