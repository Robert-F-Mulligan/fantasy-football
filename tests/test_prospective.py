import pytest

from fantasyfootball.evaluation.prospective import MomentumStudy


def report(week, count=2, b=6, c=4, **changes):
    shadow = {
        "status": "scored",
        "candidate": "workload_momentum_v1",
        "protocol_window": True,
        "paired_rows": count,
        "baseline_absolute_error_sum": b,
        "candidate_absolute_error_sum": c,
        "by_position": {
            "RB": {
                "paired_rows": count,
                "baseline_absolute_error_sum": b,
                "candidate_absolute_error_sum": c,
            }
        },
    }
    return dict(
        season=2026,
        week=week,
        archive_sha256=f"forecast-{week}",
        captured_at="2026-11-01T00:00:00Z",
        unresolved_rows=1,
        pregame_rows=3,
        confirmed_dnp_rows=0,
        shadow=shadow,
        **changes,
    )


def summarize(reports, week=12):
    return MomentumStudy().summarize(
        reports,
        current_season=2026,
        current_week=week,
        outcome_archive_sha256="outcome",
    )


def test_weighted_errors_not_average_of_weekly_maes():
    result = summarize([report(9, 1, 10, 5), report(10, 9, 9, 18)])
    assert result["paired_weeks"] == 2
    assert result["descriptive_totals"]["baseline_mae"] == 1.9
    assert result["descriptive_totals"]["candidate_mae"] == 2.3
    assert result["by_position"]["RB"]["paired_rows"] == 10
    assert result["weeks"][2]["status"] == "missing_capture"
    assert result["weeks"][3]["status"] == "not_yet_captured"
    assert result["status"] == "collecting"


def test_missing_shadow_is_retained_and_duplicate_weeks_rejected():
    missing = report(9)
    missing["shadow"] = {"status": "not_recorded"}
    result = summarize([missing])
    assert (
        result["paired_weeks"] == 0 and result["weeks"][0]["status"] == "not_recorded"
    )
    assert result["descriptive_totals"]["mae_delta"] is None
    with pytest.raises(ValueError, match="Duplicate week"):
        summarize([missing, report(9)])


def test_readiness_requires_closed_window_and_eight_weeks_not_effect_threshold():
    reports = [report(w, 2, 1, 100) for w in range(9, 17)]
    assert summarize(reports, 17)["status"] == "collecting"
    result = summarize(reports, 18)
    assert (
        result["status"] == "ready_for_final_analysis"
    )  # Even a worse candidate needs honest analysis.
    assert "no interim significance" in result["inference"]
    assert summarize(reports[:-1], 18)["status"] == "insufficient_paired_weeks"


def test_preview_week_excluded_and_unknown_protocol_rejected():
    assert summarize([report(8)])["paired_weeks"] == 0
    bad = report(9)
    bad["shadow"]["candidate"] = "changed_model"
    with pytest.raises(ValueError, match="Unexpected"):
        summarize([bad])


@pytest.mark.parametrize(
    "field,value",
    [
        ("paired_rows", 0),
        ("paired_rows", 2.5),
        ("baseline_absolute_error_sum", -1),
        ("candidate_absolute_error_sum", float("nan")),
    ],
)
def test_corrupt_weekly_totals_fail(field, value):
    bad = report(9)
    bad["shadow"][field] = value
    with pytest.raises(ValueError, match="Invalid"):
        summarize([bad])


def test_archive_writes_private_monitor_using_earliest_missing_candidate(
    tmp_path, monkeypatch
):
    import json
    from types import SimpleNamespace
    from zipfile import ZipFile

    from fantasyfootball.evaluation import scorecard_archive as module

    current_path = tmp_path / "current.zip"
    with ZipFile(current_path, "w") as archive:
        archive.writestr("context/games.csv", "season,week\n2026,10\n")
        archive.writestr(
            "league/import-report.json",
            json.dumps({"league_id": "league", "roster_id": 1}),
        )
    checkout = tmp_path / "repo"
    snapshots = checkout / "snapshots/2026/week-09"
    snapshots.mkdir(parents=True)
    for name, day in [("first", "01"), ("later", "02")]:
        with ZipFile(snapshots / (name + ".zip"), "w") as archive:
            archive.writestr(
                "evidence-manifest.json",
                json.dumps(
                    {
                        "season": 2026,
                        "week": 9,
                        "captured_at": f"2026-11-{day}T00:00:00Z",
                    }
                ),
            )
            archive.writestr(
                "league/import-report.json",
                json.dumps({"league_id": "league", "roster_id": 1}),
            )
    current = SimpleNamespace(
        manifest={"season": 2026, "week": 10, "captured_at": "2026-11-08T00:00:00Z"},
        sha256="latest",
    )
    loaded = []

    def load(path):
        loaded.append(path.name)
        return (
            current
            if path == current_path
            else SimpleNamespace(manifest={"season": 2026, "week": 9})
        )

    missing = report(9)
    missing["shadow"] = {"status": "not_recorded"}
    monkeypatch.setattr(module, "ArchivedForecast", load)
    monkeypatch.setattr(module, "observed_outcomes", lambda *args: None)
    monkeypatch.setattr(
        module.WeeklyScorecard, "evaluate", lambda *args: (missing, None)
    )
    added = module.build_private_scorecards(current_path, checkout)
    assert loaded == ["current.zip", "first.zip"]
    assert len(added) == 1 and added[0].startswith("studies/workload_momentum_v1/")
    result = json.loads((checkout / added[0]).read_text(encoding="utf-8"))
    assert (
        result["weeks"][0]["status"] == "not_recorded" and result["paired_weeks"] == 0
    )
    assert module.build_private_scorecards(current_path, checkout) == []
