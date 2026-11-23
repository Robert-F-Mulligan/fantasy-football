# Prospective availability evidence

The private archive already seals fetched player JSON, availability, forecasts, source times, and checksums. The availability-history evaluator derives a structured history from verified archives without fetching or backdating new historical data.

## Automatic private output

Each private archive publication with scorecards enabled writes an append-only `availability-history/<league-scope>/<outcome-archive-hash>.json`. The existing workflow enables scorecards; no new secret, email, or external data service is required. Snapshots belonging to other leagues/owners or captured later than the outcome snapshot are excluded. Retrying the same outcome snapshot does not overwrite its result.

For each offensive player on the owner's roster, the history retains the source archive hash, provider fetch time, actual capture time, kickoff, pregame eligibility, scoring-rule hash, model eligibility, recorded injury designation, practice fields when supplied, and frozen point forecast when available. Unknown fields remain unknown. The provider's general Active status is not a confirmed game-day active list.

A designation-removal event requires an explicitly populated designation followed by an explicitly empty designation in a newer fetched snapshot. A missing field or a repeated/older source observation does not establish removal. This event means the designation was no longer reported; it does not establish medical clearance or a restored workload.

## Follow-up policy

Choose the earliest retained capture per league/owner/player/week before looking at results. Preserve late or unknown-kickoff captures as excluded; never replace them with a later favorable rerun. Outcome scoring reuses the existing settled-week checks: a later report week, completed game scores, at least eight hours after the last kickoff, and observed statistics for all scheduled teams.

Recorded box scores can establish observed points. A missing box score stays unresolved; it is never inferred to be DNP or zero. Explicit finalized DNP evidence can be scored only with zero points and a source, but the automatic box-score adapter does not manufacture such records. Changed scoring rules cannot silently score an earlier forecast. An absent forecast is coverage missingness, not a zero forecast.

Observed-only MAE is descriptive and subject to coverage bias. No interim significance tests, model promotion, or claims about medical availability are produced. In particular, an earliest forecast may precede a later designation removal; both observations are retained, but the later one is not substituted into the primary evaluation. A separate predeclared return-to-play study will need timestamped inactive/active evidence and its own selection policy.

## Validation

Tests cover explicit-null versus missing designation, stale-source transitions, earliest-capture policy, late exclusions, unresolved missing box scores, finalized outcomes, absent forecasts, scoring-rule mismatch, and a real sealed-archive round trip with idempotent output. A private saved-snapshot replay also verifies that pregame outcomes remain unresolved until settled evidence exists.
