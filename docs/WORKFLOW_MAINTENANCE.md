# Workflow maintenance

Updated October 29, 2026. Both workflows pin the official actions to immutable commit SHAs:

| Action | Release | Commit |
| --- | --- | --- |
| checkout | [v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| setup-python | [v7.1.0](https://github.com/actions/setup-python/releases/tag/v7.1.0) | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |

Release tags were resolved through the official GitHub API, and each pinned action.yml declares node24. GitHub-hosted runners supply the runtime; any future self-hosted runners must meet the upstream minimum runner requirements. Checkout continues to disable credential persistence. No unsafe PR checkout option is enabled.

The Ubuntu 24.04 runner image is explicit to avoid an unreviewed OS transition through ubuntu-latest. This pins the OS family, not every runner package. Python library versions remain governed by pyproject ranges; a fully locked dependency environment is still future work.

CI includes Python 3.10/3.12 tests and wheels, PostgreSQL/dbt checks, and a separate hosted-report runtime job. That job installs only model/scraping extras plus pytest, asserts Plotly/SQLAlchemy are absent, and runs offline report and delivery-boundary tests. It uses no league credentials and sends no mail. This catches accidental dependencies hidden by the larger development installation.

The production report workflow remains main-only. Tuesday/Wednesday schedules, send reservations and private-archive handling are unchanged. Its next main-branch push runs the real data refresh and archive checks without sending email; verify that run after merging action updates. PR runtime checks cannot verify SMTP delivery or secrets.

For future updates, inspect official release notes, resolve the release to a full SHA, update both workflows, verify CI including report-runtime, then verify the merge-triggered email-free production preparation. Keep action versions out of mutable major-version references.
