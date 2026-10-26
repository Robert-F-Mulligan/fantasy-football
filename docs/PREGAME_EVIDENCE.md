# Pregame evidence and availability experiment

The role-change/injury experiment is gated on trustworthy pregame inputs. No new availability model has been fitted or promoted.

## Historical input audit

Downloaded nflverse injury files on October 25, 2026 and compared regular-season row modification times with Wednesday 10 a.m. America/New_York for each scheduled game week.

| Season | Regular-season injury rows | Last modified by Wednesday cutoff | Result |
|---|---:|---:|---|
| 2023 | 5,451 | 28 (0.51%) | Insufficient Wednesday history |
| 2024 | 5,954 | 56 (0.94%) | Insufficient Wednesday history |
| 2025 | 5,783 | Timestamp column absent | Cannot establish availability at cutoff |
| 2026 | 2,139 | Timestamp column absent | Cannot establish availability at cutoff |

A row's modification date is not proof that the whole feed was captured at that time. Filtering out later rows would not reconstruct earlier injury reports, and treating absent rows as healthy would bias the experiment. Therefore all four files are rejected for a Wednesday injury-status backtest. This does not mean the source data is unusable for other questions or that the few early rows prove a predictive effect.

Source files: `https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv`. Checksums and counts are in `availability-input-audit.json`. Provider documentation: https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html and https://docs.sleeper.com/ .

Reproduce with downloaded files:

```powershell
python examples/audit_availability_inputs.py --schedule work/hosted-ranges-preview/context/games.csv --injuries work/availability-audit/injuries-2023.csv work/availability-audit/injuries-2024.csv work/availability-audit/injuries-2025.csv work/availability-audit/injuries-2026.csv --output work/new-availability-audit.json
```

## Capture the next forecasts

The hosted prepare command can now retain a private local evidence ZIP:

```powershell
python -m fantasyfootball.reports.hosted prepare --output work/new-report --archive work/private-evidence
```

It uses the existing FF_LEAGUE_ID, FF_TEAM_NAME and FF_SEASON environment variables. Preparation does not send an email. Each capture uses a unique, exclusively created file; rerunning cannot replace earlier predictions. Files contain sensitive league rosters and should remain in ignored work/ or a private storage location.

To export an existing report or verify an archive:

```powershell
python -m fantasyfootball.archives.evidence capture --report work/new-report --archive work/private-evidence
python -m fantasyfootball.archives.evidence verify work/private-evidence/2026/week-08/ARCHIVE.zip
```

The bundle includes an explicit allowlist of schedule/player-status inputs, league scoring and rosters, the versioned stats snapshot, offensive projections, availability, lineup, and optional specialist context. SMTP configuration, environment files, recipient mail and rendered reports are excluded. File SHA-256 checksums are verified before capture and again when checking the bundle. New prepared forecasts record generating code hashes and dependency versions; old exports explicitly lack that provenance. Capture-runtime information is labeled separately.

Per-player eligibility requires capture strictly before that player's recorded kickoff. Unknown kickoff, exactly-at-kickoff and later captures are ineligible. A historical as_of argument cannot backdate capture. Future source timestamps and same-week training cutoffs are rejected. Pregame eligibility describes timing only; it does not mean the player will play or establish a DNP label. A missing box score must remain unresolved until reconciled against participation/game data.

These are local integrity records, not encrypted archives or independently timestamped signatures. Verification reads members without extracting them. Retain the generated code commit as well as its hashes if exact future reruns are required.

## Current activation and validation

A live Sleeper/nflverse preparation completed successfully and saved a verified 6.6 MB private archive. All 15 roster rows were correctly ineligible because their games had already kicked off. No email was sent. This validates capture behavior, not forecast accuracy or an injury-model advantage.

The Python suite passes (122 tests), including archive integrity, duplicate capture preservation, allowlist exclusions, exact kickoff boundaries, historical backdating rejection, future-source rejection and invalid training cutoffs.

The workflow now supports private GitHub retention when FF_ARCHIVE_REPOSITORY is configured. Before email delivery, it verifies the archive, checks that the destination is not anonymously visible, pushes with a dedicated SSH deploy key, fetches the result and compares the exact Git blob. A failed configured upload stops delivery and marks the run failed. No public Actions artifacts contain the evidence. The existing Wednesday schedule remains unchanged.

The destination is Robert-F-Mulligan/fantasy-football-evidence, created and confirmed private. Activation still requires the owner's authenticated setup command below. The deploy key has write access to this one repository and is held in the source repository's FF_ARCHIVE_SSH_KEY Actions secret; it is not an account-wide token. Setup verifies authenticated metadata private=true. Runtime uses an anonymous 404 check plus successful authenticated SSH access, rejects public/redirected/unavailable responses, and checks visibility again immediately before push. Do not change the archive repository to public; these checks cannot make a simultaneous visibility change atomic.

After the reviewed workflow is merged, run from the repository in your authenticated PowerShell:

```powershell
.\ff-venv\Scripts\python.exe scripts/setup_private_archive.py --gh .\work\github-cli\bin\gh.exe
```

The script checks login and repository privacy, generates a fresh deployment key, installs its public half on the private repository, encrypts the private half into the source Actions secret through gh stdin, removes temporary key files, sets the destination variable and dispatches an email-free test. It never prints private keys. If saving the secret fails, it revokes the just-created deploy key. A subsequent failure leaves the configuration available for diagnosis; avoid rerunning setup unnecessarily, since each completed setup creates a new key. Revoke superseded keys in the private repository settings after any rotation.

Archives are retained as content-addressed files under snapshots/SEASON/week-WW with Git history; no automatic pruning is enabled. Weekly bundles are currently about 6.6 MB. Monitor repository size as seasons accumulate; migrations or retention changes should preserve the evaluation record. Deploy keys have no automatic expiry, so revoke this key if the automation is retired. GitHub host keys come from the HTTPS metadata API and SSH strict host verification stays enabled.

## Next experiment protocol

1. Collect Wednesday snapshots before kickoff. Record actual observation time, forecast-generation time, provider IDs, current team, public injury/status feed, prior usage and the full eligible candidate population. Preserve missing values rather than inferring healthy status.
2. Before seeing outcomes, freeze a simple prior-four-games points benchmark and candidate features: team changes, changes in prior snap/target share, and prior opportunity held by teammates explicitly known unavailable at capture. Do not use final active lists as Wednesday features.
3. Reconcile outcomes using final game/participation evidence. Distinguish bye, DNP, actual zero, partial game and missing data. Keep injury probability and conditional-on-playing points separate.
4. Select on earlier weeks and evaluate on later weeks, resampling complete weeks. Score the full eligible population and actual roster-constrained lineup regret, including RB/WR/TE FLEX and kickoff locks. Current same-position pair tests are only a proxy.
5. Require the existing improvement gates plus adequate availability calibration before production promotion. Do not select features repeatedly against the already inspected 2024 or 2026 holdouts. Draft-day forecasts require a separate season-level evaluation.
