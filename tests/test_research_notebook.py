"""Execute supported, reviewed notebooks from an empty namespace without Jupyter."""

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "name, variable, count",
    [
        ("Weekly-Player-Research", "selected", 8),
        ("Receiver-Usage", "usage", 3),
        ("Team-Matchups", "comparison", 6),
        ("Neutral-Tendencies", "tendencies", 2),
    ],
)
def test_supported_notebook_runs_offline(monkeypatch, name, variable, count):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root / "notebooks" / "current")
    filename = name + ".ipynb"
    notebook = json.loads((Path.cwd() / filename).read_text(encoding="utf-8"))
    namespace = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [] and cell["execution_count"] is None
            exec(  # noqa: S102 - fixed allowlist of checked-in, reviewed notebooks
                compile("".join(cell["source"]), filename, "exec"), namespace
            )
    assert len(namespace[variable]) == count
    if name == "Weekly-Player-Research":
        assert namespace["summary"].games.sum() == 8
        assert namespace["export"] is False
    if name == "Receiver-Usage":
        assert namespace["audit"]["identified_targets"] == 3
