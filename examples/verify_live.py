"""Bounded live checks; never writes persistent source data or prints credentials."""

import json
from pathlib import Path
import requests
from sqlalchemy import create_engine, text
from fantasyfootball.connectors.sql_connector import SqlConnector
from fantasyfootball.connectors.github_connector import GitHubConnector
from fantasyfootball.facade.data_facade import DataFacade, load_config


def verify():
    results = {}
    try:
        engine = create_engine(
            SqlConnector().construct_url(), connect_args={"connect_timeout": 10}
        )
        with engine.connect() as connection:
            connection.execute(
                text(
                    "create temporary table ff_integration_probe (value integer) on commit drop"
                )
            )
            connection.execute(text("insert into ff_integration_probe values (17)"))
            assert (
                connection.execute(
                    text("select value from ff_integration_probe")
                ).scalar()
                == 17
            )
            connection.rollback()
        engine.dispose()
        results["postgres"] = {
            "status": "passed",
            "check": "connect / temporary write / read / rollback",
        }
    except Exception as exc:
        results["postgres"] = {"status": "failed", "error_type": type(exc).__name__}
    try:
        projections = DataFacade(load_config()).get_data(
            "fantasy_pros_projections", request_delay=0
        )
        assert len(projections) > 0 and projections.player_id.notna().all()
        assert projections.loc[projections.pos == "RB", "receiving_rec"].sum() > 0
        results["fantasypros"] = {
            "status": "passed",
            "rows": len(projections),
            "scope": "public preview only; not a complete draft pool",
        }
    except Exception as exc:
        results["fantasypros"] = {"status": "failed", "error_type": type(exc).__name__}
    try:
        reader = GitHubConnector("https://github.com").fetch(
            "nflverse/nflverse-data/releases/download/pbp/play_by_play_2023.csv.gz",
            chunksize=1000,
        )
        with reader:
            sample = next(iter(reader))
        assert len(sample) == 1000 and sample.game_id.notna().all()
        results["nflverse"] = {"status": "passed", "rows_sampled": len(sample)}
    except Exception as exc:
        results["nflverse"] = {"status": "failed", "error_type": type(exc).__name__}
    try:
        response = requests.get(
            "https://www.pro-football-reference.com/years/2023/fantasy.htm", timeout=25
        )
        results["pfr"] = {
            "status": "blocked"
            if response.status_code in (401, 403, 429)
            else "http_checked",
            "http_status": response.status_code,
        }
    except Exception as exc:
        results["pfr"] = {"status": "failed", "error_type": type(exc).__name__}
    return results


if __name__ == "__main__":
    results = verify()
    Path("work").mkdir(exist_ok=True)
    Path("work/live_verification.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, indent=2))
    raise SystemExit(
        1 if any(result["status"] == "failed" for result in results.values()) else 0
    )
