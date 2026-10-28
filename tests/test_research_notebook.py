"""Run supported notebook cells from a clean namespace without a Jupyter dependency."""

import json
from pathlib import Path


def test_weekly_research_notebook_runs_offline(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root / "notebooks" / "current")
    notebook = json.loads(
        (Path.cwd() / "Weekly-Player-Research.ipynb").read_text(encoding="utf-8")
    )
    namespace = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [] and cell["execution_count"] is None
            exec(  # noqa: S102 - execute only this checked-in, reviewed notebook
                compile(
                    "".join(cell["source"]), "Weekly-Player-Research.ipynb", "exec"
                ),
                namespace,
            )
    assert len(namespace["selected"]) == 8
    assert namespace["summary"].games.sum() == 8
    assert namespace["export"] is False
