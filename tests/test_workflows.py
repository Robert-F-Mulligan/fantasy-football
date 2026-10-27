from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize("filename", ["tests.yml", "weekly-report.yml"])
def test_workflows_parse_and_run_steps_are_strings(filename):
    path = Path(__file__).resolve().parents[1] / ".github/workflows" / filename
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert workflow["on"]
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "run" in step:
                assert isinstance(step["run"], str)
    if filename == "weekly-report.yml":
        assert workflow["on"]["schedule"][0]["timezone"] == "America/New_York"


def test_separate_tuesday_waivers_and_wednesday_lineups():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/weekly-report.yml"
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert {entry["cron"] for entry in workflow["on"]["schedule"]} == {
        "0 10 * * 2",
        "0 10 * * 3",
    }
    assert all(
        entry["timezone"] == "America/New_York" for entry in workflow["on"]["schedule"]
    )
    assert (
        "github.event.schedule == '0 10 * * 2'"
        in workflow["jobs"]["report"]["env"]["REPORT_TYPE"]
    )
    assert '--report-type "$REPORT_TYPE"' in next(
        s["run"]
        for s in workflow["jobs"]["report"]["steps"]
        if s.get("name") == "Refresh data and prepare report"
    )
