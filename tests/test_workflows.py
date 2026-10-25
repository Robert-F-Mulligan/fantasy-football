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
