# Hosted Wednesday email report

The GitHub Actions workflow runs on GitHub's Ubuntu runner. Your PC and desktop app can be off after cutover. It is scheduled for Wednesdays at 10 a.m. America/New_York, with daylight saving handled by GitHub. GitHub can delay or drop scheduled jobs; this is not a guaranteed 10:00 delivery service. Public-repository schedules can be disabled after 60 days without activity.

## One-time setup

1. Push the branch and merge PR #10 after CI passes. Scheduled and manually dispatched workflows must exist on the default branch (`main`).
2. Create a Gmail app password for this workflow using Google's account settings. It requires 2-Step Verification and is unavailable for some accounts. Do not use your regular Google password, paste the app password into chat, or commit it. The Gmail connector in the desktop app does not provide credentials to GitHub Actions.
3. Run `./scripts/configure-hosted-report.ps1` from an authenticated PowerShell. It sets league/team/season variables and prompts through `gh` for `REPORT_EMAIL_TO`, `GMAIL_USERNAME`, and `GMAIL_APP_PASSWORD`. Use `your Gmail address` for the first two. The script does not activate email.
4. In GitHub Actions, run **Wednesday fantasy report** on `main` with `send_email=false`. A successful report prints `ready`; `offseason` means no upcoming regular-season game was found. Failures are real blockers, not successful deliveries. Personal report contents are intentionally not uploaded as public artifacts or printed in job logs.
5. After the dry run succeeds, pause the desktop automation `bower-rangers-wednesday-start-sit-report` to avoid two independent senders. Then set repository variable `REPORT_EMAIL_ENABLED=true` and manually run with `send_email=true` for the first hosted delivery. Confirm the email arrived and the job reports `sent`. Do not leave both schedules active.
6. Subsequent Wednesday runs send once per recipient, league, season and week. Update the season and league ID for a future league rather than silently following another league.

Variables and secrets can also be entered under repository Settings → Secrets and variables → Actions. Never put the app password in an issue, PR, workflow YAML or shell command argument. Gmail secrets are available only to the report job; the CI test workflow receives none. The report job only runs on main in the original repository and is never triggered by PR contents.

## Delivery semantics and recovery

A `report-delivery-state` branch stores hashed delivery keys and Message-IDs, not reports, email addresses or credentials. The job has contents-write permission to maintain this ledger. It records `pending` **before** SMTP, then `sent` after Gmail accepts the message. A second run skips a sent key. A pending key blocks retries: this deliberately prioritizes avoiding duplicate mail over automatic retry after an ambiguous failure.

If a run fails after reservation, inspect Gmail Sent for the Message-ID from the ledger. If already sent, mark the record sent. Delete a pending record only after confirming no email was sent; then rerun. SMTP acceptance does not prove inbox placement. If the ledger update fails after SMTP acceptance, the next run remains blocked rather than resending. Do not delete the state branch during cleanup.

## Data and model scope

Each run downloads a fresh schedule, player status, canonical IDs and two prior seasons plus current-season stats (from week 2 onward). It selects the next regular-season game week in the configured season, checks that the previous week's games have scores and both teams have player-stat coverage, then trains only on earlier weeks. This team-level check does not prove every individual player record is present.

The email includes start/sit choices, projected points, opponents, availability warnings, changes from imported starters, and nominal 80% historical error ranges with later-week coverage checks. It uses the existing offensive model; defense forecasts, full special-teams scoring, individual volatility estimates and formal coverage guarantees remain unfinished. Kicking-only baselines are reported separately as described below. Infeasible plans and stale inputs fail without sending advice. This job has no LLM API dependency and does not submit lineup changes.

## Verification

Local live preparation completed on October 24, 2026 and produced the week-7 HTML/plain-text report. SMTP behavior and reservation/retry behavior are tested with fakes. Hosted preparation and Gmail SMTP delivery were verified on October 25, 2026 (Actions run 40201365106), and the user confirmed inbox receipt. REPORT_EMAIL_ENABLED is true and the desktop schedule is paused. PostgreSQL/dbt are not used by this workflow.

Official references: [GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [Gmail app passwords](https://support.google.com/mail/answer/185833).


Changes to the application or report workflow merged into main also trigger an automatic email-free hosted dry run. Workflow syntax is parsed by regression tests; the dependency-version command uses a YAML block scalar so Python dictionary colons cannot invalidate it. Mail remains restricted to the Wednesday schedule or an explicit `send_email=true` dispatch.


## Kicker and defense coverage

Reports include a separate specialist section with actual Sleeper slots, opponents, kickoffs, injury/byes and kickoff locks. The offensive table now names assigned slots, including FLEX1.

Kicker estimates use the last eight observed current-team games, shrunk toward the recent league kicker average with four games of prior weight. At least four current-team observations are required. These are kicking-only research baselines, not the offensive factor model; they exclude rare offensive contributions, weather, opponent effects and DNP probabilities. No calibrated kicker interval or superiority over expert projections is claimed. Unknown kicking rules disable these estimates, and only single-kicker leagues receive baseline start/bench labels. Defense remains context-only, without point forecasts or start/sit advice.

Kicking scores include blocked FG/PAT misses and stack general and distance-specific penalties. A live comparison matched all 68 available rostered kicker scores from this league's 2026 weeks 1?6. This validates those scoring observations, not future prediction quality.

References: [nflverse player statistics](https://nflreadr.nflverse.com/articles/dictionary_player_stats.html), [Sleeper scoring rules](https://support.sleeper.com/en/articles/3998131-what-scoring-options-are-available). Defense scoring still needs play-level reconciliation because [Sleeper points allowed](https://support.sleeper.com/en/articles/4126495-how-are-points-allowed-calculated) differs from the game's final score.
