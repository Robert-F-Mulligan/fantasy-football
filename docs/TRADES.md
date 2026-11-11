# Roster-relative rest-of-season trade value

The Tuesday 10 a.m. Eastern digest assesses every offensive position without a fixed RB/QB/WR/TE priority. Its objective is the change in your **expected remaining-season starting-lineup points**, relative to the roster you already have and the currently available waiver alternatives. The default window runs from the next unstarted week through week 17. It assumes the team continues playing throughout that window; playoff qualification probabilities and future-season keeper value are not included.

## Valuation

One pregame weekly model is fit on prior weeks only. Each remaining week's fixtures are predicted separately using current historical features, opponent schedules, and league-supported scoring. Predicted outcomes never become training data. Current injuries and roles are held unchanged; this is not a validated multi-week injury-recovery or role-change model.

Waiver candidates reuse canonical ownership checks, including provider IDs, canonical IDs, and unresolved owned IDs. Only modeled offensive players with at least four historical appearances are considered. Up to four distinct projected alternatives per position per week enter the lineup optimizer. No single player can fill two slots, including FLEX. Streaming is an optimistic counterfactual: claim competition, FAAB, waiver timing, and drop/reacquisition costs are not modeled. These assumptions are applied to both sides consistently, so a QB bye does not automatically create a zero-point baseline and an inflated trade premium.

Depth contributes through 128 fixed-seed availability scenarios per week, shared before and after every proposal. Participation probabilities use Laplace-smoothed scoring-appearance rates over up to eight past current-team scheduled opportunities since the player's first observed appearance there; players without current-team evidence use a position-pooled fallback. This is an **uncalibrated availability proxy**, not a clinical injury probability or a medical prediction. Byes and known unavailable players remain explicit. The optimizer uses forecast points in each availability scenario, not sampled realized scores; it does not choose starters with hindsight about their fantasy scores. Future availability, claim access, and player roles need separate backtesting before treating these expected values as calibrated guarantees.

The package score is `value(roster after trade and drops) - value(current roster)`. The report decomposes it into incoming marginal benefit and outgoing opportunity cost. Future pick indices remain in separate units and are never added to lineup points. Missing owned-player forecasts block the comparison rather than becoming zero points.

## Relative strengths and targets

The position table measures the roster value lost when each position's players are removed and waiver alternatives take their place. It compares that marginal value with other evaluable teams at the **same position**, reporting the league median and rank. FLEX and bench cover are included. These overlapping position contributions must not be summed; they explain a roster's strengths, not a fixed preference for buying one position.

The acquisition-target list ranks the greatest expected improvement if an outside player were acquired and one movable roster player displaced. It accounts for the displaced player's opportunity cost but **does not include the price the other manager will demand**. A displaced player is a roster-space counterfactual, not a suggested fair offer. Separately, the digest scans one-for-one packages and reports those with positive expected gains for both teams, ordered by your gain. No arbitrary position floor or single-week veto overrides the marginal-value objective. If no package qualifies, the email says so. Offers and roster changes are never submitted.

## Custom calculator

Prepare privately using existing league environment variables:

```powershell
$env:FF_TRADE_RULES='config/trade-rules.json'
python -m fantasyfootball.reports.hosted prepare --output work/trade-digest --report-type trades
python -m fantasyfootball.trading --plan work/trade-digest/plan --partner 2 --give player-id-a player-id-b --receive player-id-c --partner-drop player-id-d --output work/trade-comparison.json
```

Use canonical player IDs and roster IDs from `trade-rosters.csv`. Explicit drops are required when a package would increase either team's active offensive roster size; open slots are conservatively not assumed. Ownership, duplicates, overlapping lists, and inactive trade candidates are checked. Saved replacement forecasts and participation evidence are required when reloading an ROS report, so the CLI cannot silently fall back to a different valuation method. Refresh old snapshots before acting.

## Next-year picks

Sleeper's draft configuration and traded-pick ledger establish assets with immutable `year:round:original-roster` IDs and separate current owners. Confirmed league/year rules live in `config/trade-rules.json`, selected by `FF_TRADE_RULES`. This league's 2027 draft is user-confirmed as 15 rounds. If next-year configuration is missing elsewhere, previous draft rounds are explicitly provisional. A conflicting configured draft fails clearly. Auction formats and ambiguous configurations do not generate numbered picks.

```powershell
python -m fantasyfootball.trading --plan work/trade-digest/plan --partner 2 --give-picks 2027:1:3 --receive player-id-c --drop player-id-a --output work/pick-trade.json
```

Pick-only and player-for-pick proposals validate ownership. They report current-season lineup effects separately from **unpriced future fair value**. The optional draft-capital index is `100 / sqrt(overall_pick)`, an unvalidated rank heuristic. It is neither a fantasy-point projection nor an empirical trade-price curve. Do not sum those units. With reverse-standings rules it follows the original team's current winning percentage, points-for tiebreaker, and snake reversal; unknown ordering retains a uniform estimate and a separately labeled conditional reverse-standings scenario. It does not model playoffs or lotteries. Keeper costs and the actual next-year player pool remain unspecified. No fair-price pick recommendations are made.

## Deadline and hosting

The email explains that Sleeper trading closes at the **end** of the final game in the selected deadline week, and trades accepted before it can finish review afterward. Since the final whistle has no fixed timestamp, email preparation and sending conservatively stop at that game's **kickoff**. This is an email cutoff, not the league's deadline. Live rules and schedule are checked independently before preparation and before SMTP. Unknown deadline data fails closed; suppressed runs skip SMTP, reservations, and empty archives. Waiver and lineup reports are unaffected.

Tuesday waiver/trade jobs run sequentially and use separate delivery keys. Merge-triggered preparations do not send. Rosters, projections, replacement candidates, participation evidence, pick inventory, and report JSON are archived only in the existing private repository. No personal artifacts are uploaded publicly.

## Validation and limits

Tests cover roster-dependent position targets, replacement-adjusted bye value, useful bench depth, FLEX uniqueness, ownership, full remaining-season forecasting without leakage, deterministic shared scenarios, proposal accounting, pick transfers, and deadline suppression. The scenario engine is validated for mechanics, not empirical trade performance. Season-long role forecasting, availability calibration, acquisition friction, multi-player automatic proposal search, and future pick fair pricing remain open work.

Sources: [Sleeper API](https://docs.sleeper.com/), [trade deadline rules](https://support.sleeper.com/en/articles/2435411-when-is-my-trade-deadline).
