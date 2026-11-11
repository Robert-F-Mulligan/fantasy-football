# In-season trade calculator and digest

The hosted trade digest runs Tuesday at 10 a.m. America/New_York alongside the waiver email. Each report has its own delivery key. Jobs run sequentially so private archive and delivery-ledger writes do not race. Merge-triggered lineup/trade runs prepare reports without sending; manual dispatch offers `trades` and a separate send switch. Existing Gmail credentials and email activation apply.

## What the values mean

The calculator optimizes both teams' offensive starters before and after each proposal, using imported slot eligibility including FLEX. A value of +12 means twelve additional projected starting-lineup points over the displayed weeks, not twelve points per week or a player market price. The digest scans one-for-one swaps, keeps positive gains for both sides at one-decimal display precision, sorts by your gain, and shows at most one proposal per partner. That rounding filter is not a statistical-significance test. Weekly tables expose negative weeks and bye coverage behind the total.

One pregame weekly model is fit on prior weeks only. Future fixtures are predicted independently with current historical features; predicted outcomes never become training data. The default horizon is four weeks, capped at week 17. If any game in the current week has started, the comparison starts next week. The league's trade deadline is respected; after it closes the digest reports that status without suggesting trades. Trade-review delays are not simulated.

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
