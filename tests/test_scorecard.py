import json
from types import SimpleNamespace

import pandas as pd
import pytest

from fantasyfootball.forecasting.features import STATS
from fantasyfootball.evaluation.scorecard import (
    ArchivedForecast,
    FinalOutcomes,
    WeeklyScorecard,
    scoring_digest,
    write_scorecard,
)


def forecast():
    roster = pd.DataFrame(
        {
            "player_id": ["a", "b", "c"],
            "sleeper_id": ["1", "2", "3"],
            "player_name": ["A", "B", "C"],
            "pos": ["RB", "WR", "TE"],
            "kickoff": ["2024-09-08T17:00:00Z"] * 3,
            "availability": ["eligible"] * 3,
            "locked_slot": [""] * 3,
        }
    )
    predictions = pd.DataFrame(
        {
            "player_id": ["a", "b", "c"],
            "projected_points": [6.0, 10.0, 15.0],
            "prediction_lower": [0.0, 10.0, 5.0],
            "prediction_upper": [10.0, 15.0, 15.0],
            "range_status": ["estimated"] * 3,
            "range_target_coverage": [0.8] * 3,
        }
    )
    return SimpleNamespace(
        manifest={
            "season": 2024,
            "week": 1,
            "captured_at": "2024-09-04T14:00:00Z",
            "eligibility": [
                {
                    "sleeper_id": i,
                    "pregame_evidence": True,
                    "reason": "captured_before_kickoff",
                }
                for i in ["1", "2", "3"]
            ],
        },
        sha256="test",
        scoring={"receiving_rec": 1},
        slots={"RB1": ["RB"], "FLEX1": ["RB", "WR", "TE"]},
        roster=roster,
        projections=predictions,
        lineup=pd.DataFrame({"slot": ["RB1", "FLEX1"], "player_id": ["a", "c"]}),
        baseline=lambda: pd.DataFrame(
            {
                "player_id": ["a", "b", "c"],
                "baseline_points": [6.0, 9.0, 7.0],
                "baseline_games": [4] * 3,
            }
        ),
    )


def outcomes():
    return {
        "season": 2024,
        "week": 1,
        "scoring_sha256": scoring_digest({"receiving_rec": 1}),
        "players": [
            {
                "player_id": p,
                "status": "played",
                "points": n,
                "source": "verified fixture",
                "finalized_at": "2024-09-10T00:00:00Z",
            }
            for p, n in [("a", 5), ("b", 20), ("c", 10)]
        ],
    }


def test_same_population_baseline_range_coverage_and_flex_regret():
    report, _rows = WeeklyScorecard().evaluate(forecast(), outcomes())
    assert report["paired_rows"] == 3
    metrics = {
        m["model"]: m
        for m in report["point_metrics"]
        if m["population"] == "all_resolved" and m["position"] == "ALL"
    }
    assert metrics["model"]["mae"] == pytest.approx(16 / 3)
    assert metrics["recent4"]["mae"] == 5
    assert report["lineup"]["recommended_regret"] == 10
    assert report["lineup"]["baseline_regret"] == 0
    assert report["lineup"]["includes_flex"]
    assert {r["position"]: r["coverage"] for r in report["prediction_ranges"]} == {
        "RB": 1,
        "WR": 0,
        "TE": 1,
    }


def test_missing_bench_outcome_blocks_regret_and_never_becomes_zero():
    final = outcomes()
    final["players"].pop(1)
    report, rows = WeeklyScorecard().evaluate(forecast(), final)
    assert report["scored_rows"] == 2
    assert report["lineup"]["status"] == "pending"
    assert pd.isna(rows.set_index("player_id").loc["b", "points"])


def test_confirmed_dnp_counts_for_points_but_not_conditional_ranges():
    final = outcomes()
    final["players"][1].update(status="dnp", points=0)
    report, _ = WeeklyScorecard().evaluate(forecast(), final)
    assert report["confirmed_dnp_rows"] == 1 and report["paired_rows"] == 3
    assert sum(r["n"] for r in report["prediction_ranges"]) == 2
    assert report["lineup"]["baseline_regret"] == 10
    assert report["lineup"]["recommended_regret"] == 0


def test_late_forecasts_are_excluded_and_locks_are_preserved():
    data = forecast()
    data.manifest["eligibility"][0]["pregame_evidence"] = False
    report, _ = WeeklyScorecard().evaluate(data, outcomes())
    assert report["scored_rows"] == 2 and report["lineup"]["status"] == "unavailable"
    data.roster.loc[0, ["availability", "locked_slot"]] = ["locked_starter", "RB1"]
    report, _ = WeeklyScorecard().evaluate(data, outcomes())
    assert report["lineup"]["status"] == "complete"
    assert report["lineup"]["fixed_slots"] == {"RB1": "a"}


def test_scorecard_waits_without_outcomes_and_renders(tmp_path):
    report, rows = WeeklyScorecard().evaluate(forecast())
    assert report["scored_rows"] == 0 and report["lineup"]["status"] == "pending"
    write_scorecard(report, rows, tmp_path / "scorecard")
    assert (
        json.loads((tmp_path / "scorecard/scorecard.json").read_text())["paired_rows"]
        == 0
    )
    assert "Awaiting evidence" in (tmp_path / "scorecard/scorecard.html").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda d: d.update(week=2), "season/week"),
        (lambda d: d.update(scoring_sha256="bad"), "scoring"),
        (lambda d: d["players"].append(d["players"][0]), "Duplicate"),
        (lambda d: d["players"][0].update(status="dnp", points=4), "DNP"),
        (
            lambda d: d["players"][0].update(finalized_at="2024-09-01T00:00:00Z"),
            "before kickoff",
        ),
        (lambda d: d["players"][0].update(source=""), "source"),
    ],
)
def test_outcome_contract_rejects_invalid_evidence(change, match):
    final = outcomes()
    change(final)
    with pytest.raises(ValueError, match=match):
        FinalOutcomes.validate(final, forecast())


def test_baseline_uses_only_archived_preweek_history():
    data = ArchivedForecast.__new__(ArchivedForecast)
    data.manifest = {"season": 2024, "week": 5}
    data.scoring = {"receiving_rec": 1}
    data.history = pd.DataFrame(
        [
            {
                **dict.fromkeys(STATS, 0),
                "player_id": "a",
                "player_name": "A",
                "pos": "RB",
                "season": 2024,
                "week": w,
                "opp": "NYJ",
                "receiving_rec": w if w < 5 else 999,
            }
            for w in range(1, 7)
        ]
    )
    row = data.baseline().iloc[0]
    assert row.baseline_points == 2.5 and row.baseline_games == 4


def test_absent_baseline_preserves_identical_comparison_population():
    data = forecast()
    data.baseline = lambda: pd.DataFrame(
        {
            "player_id": ["a", "b"],
            "baseline_points": [6.0, 9.0],
            "baseline_games": [4, 4],
        }
    )
    report, _ = WeeklyScorecard().evaluate(data, outcomes())
    assert report["scored_rows"] == 3 and report["paired_rows"] == 2
    assert report["lineup"]["status"] == "unavailable"


def test_observed_outcomes_wait_for_completed_games_and_never_infer_dnp():
    from fantasyfootball.evaluation.scorecard_archive import observed_outcomes

    previous = forecast()
    current = SimpleNamespace(
        manifest={"season": 2024, "week": 2, "captured_at": "2024-09-11T14:00:00Z"},
        sha256="later",
        history=pd.DataFrame(
            {
                "season": [2024, 2024],
                "week": [1, 1],
                "team": ["NYJ", "NE"],
                "player_id": ["a", "z"],
                "receiving_rec": [0, 3],
            }
        ),
    )
    schedule = pd.DataFrame(
        {
            "season": [2024],
            "week": [1],
            "game_type": ["REG"],
            "home_team": ["NYJ"],
            "away_team": ["NE"],
            "home_score": [20],
            "away_score": [10],
            "gameday": ["2024-09-08"],
            "gametime": ["13:00"],
        }
    )
    final = observed_outcomes(previous, current, schedule)
    assert (
        final["players"][0]["status"] == "played" and final["players"][0]["points"] == 0
    )
    assert not any(p["player_id"] == "b" for p in final["players"])
    assert (
        observed_outcomes(previous, current, schedule.assign(home_score=None)) is None
    )
    current.manifest["week"] = 1
    assert observed_outcomes(previous, current, schedule) is None


def test_private_scorecards_choose_earliest_capture_and_save_outputs(
    tmp_path, monkeypatch
):
    from zipfile import ZipFile

    from fantasyfootball.evaluation import scorecard_archive

    previous = forecast()
    current = SimpleNamespace(
        manifest={"season": 2024, "week": 2, "captured_at": "2024-09-11T14:00:00Z"},
        sha256="later",
        history=pd.DataFrame(
            {
                "season": [2024] * 3,
                "week": [1] * 3,
                "team": ["NYJ", "NE", "NE"],
                "player_id": ["a", "b", "c"],
                "receiving_rec": [5, 20, 10],
            }
        ),
    )
    schedule = pd.DataFrame(
        {
            "season": [2024],
            "week": [1],
            "game_type": ["REG"],
            "home_team": ["NYJ"],
            "away_team": ["NE"],
            "home_score": [20],
            "away_score": [10],
            "gameday": ["2024-09-08"],
            "gametime": ["13:00"],
        }
    )
    current_path = tmp_path / "current.zip"
    with ZipFile(current_path, "w") as archive:
        archive.writestr("context/games.csv", schedule.to_csv(index=False))
        archive.writestr(
            "league/import-report.json",
            json.dumps({"league_id": "test", "roster_id": 3}),
        )
    checkout = tmp_path / "repository"
    snapshots = checkout / "snapshots/2024/week-01"
    snapshots.mkdir(parents=True)
    for name, time in [
        ("first.zip", "2024-09-04T14:00:00Z"),
        ("second.zip", "2024-09-05T14:00:00Z"),
    ]:
        with ZipFile(snapshots / name, "w") as archive:
            archive.writestr(
                "evidence-manifest.json",
                json.dumps({"season": 2024, "week": 1, "captured_at": time}),
            )
            archive.writestr(
                "league/import-report.json",
                json.dumps({"league_id": "test", "roster_id": 3}),
            )
    loaded = []

    def read(path):
        loaded.append(path.name)
        return current if path == current_path else previous

    monkeypatch.setattr(scorecard_archive, "ArchivedForecast", read)
    added = scorecard_archive.build_private_scorecards(current_path, checkout)
    assert loaded == ["current.zip", "first.zip"]
    with ZipFile(checkout / added[0]) as archive:
        report = json.loads(archive.read("scorecard.json"))
        assert (
            report["paired_rows"] == 3 and report["lineup"]["recommended_regret"] == 10
        )
        assert "scorecard.html" in archive.namelist()
        assert "outcomes.json" in archive.namelist()
    assert scorecard_archive.build_private_scorecards(current_path, checkout) == []
