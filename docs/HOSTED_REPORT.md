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

The email includes start/sit choices, projected points, opponents, availability warnings and changes from imported starters. It uses the existing offensive model; K/DEF, exact special-teams scoring and calibrated uncertainty remain unfinished. Infeasible plans and stale inputs fail without sending advice. This job has no LLM API dependency and does not submit lineup changes.

## Verification

Local live preparation completed on October 24, 2026 and produced the week-7 HTML/plain-text report. SMTP behavior and reservation/retry behavior are tested with fakes. Actual hosted execution and Gmail SMTP delivery require the user's GitHub secrets and merged workflow; they have not been verified yet. PostgreSQL/dbt are not used by this workflow.

Official references: [GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [Gmail app passwords](https://support.google.com/mail/answer/185833).
