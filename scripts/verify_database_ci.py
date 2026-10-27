"""Exercise corrected ingestion through real dbt marts in disposable schemas.

Requires DB_* credentials. Never reads or modifies the configured production
source/target schemas: all schemas are unique to this invocation.
"""

import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pandas as pd
from sqlalchemy import text

from fantasyfootball.connectors.sql_connector import SqlConnector


def main():
    connector = SqlConnector()
    engine = connector.get_engine()
    prefix = "ff_ci_" + uuid4().hex[:16]
    source = prefix + "_source"
    schemas = [
        source,
        prefix,
        *(
            prefix + "_" + suffix
            for suffix in ["staging", "intermediate", "marts", "viz"]
        ),
    ]
    env = {**os.environ, "DBT_SOURCE_SCHEMA": source, "DBT_SCHEMA": prefix}
    project = Path(__file__).resolve().parents[1] / "fantasy_football_dbt"
    dbt = [
        "dbt",
        "build",
        "--project-dir",
        str(project),
        "--profiles-dir",
        str(project),
    ]
    template = {
        "game_id": "g1",
        "season": 2025,
        "week": 1,
        "season_type": "REG",
        "game_date": "2025-09-07",
        "posteam": "BUF",
        "defteam": "NYJ",
        "play_type": "pass",
        "receiver_player_id": "a",
        "receiver_player_name": "Player A",
        "air_yards": 5.0,
        "yards_after_catch": 5.0,
        "receiving_yards": 10.0,
        "complete_pass": 1,
        "pass_touchdown": 0,
        "first_down_pass": 1,
        "yardline_100": 30.0,
        "two_point_attempt": 0,
    }
    frame = pd.DataFrame(
        [
            {**template, "play_id": 1},
            {
                **template,
                "play_id": 2,
                "receiver_player_id": "b",
                "receiver_player_name": "Player B",
            },
            {
                **template,
                "play_id": 3,
                "game_id": "g2",
                "posteam": "KC",
                "defteam": "DEN",
            },
            {**template, "play_id": 4, "two_point_attempt": 1},
            {**template, "play_id": 5, "season_type": "POST"},
        ]
    )
    created = []
    try:
        with engine.begin() as connection:
            for schema in schemas:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                created.append(schema)
            frame.head(0).to_sql(
                "nflfastr_play_by_play", connection, schema=source, index=False
            )
            connection.execute(
                text(
                    f'ALTER TABLE "{source}".nflfastr_play_by_play ADD PRIMARY KEY (game_id, play_id)'
                )
            )
        for _ in range(2):
            connector.publish(
                frame,
                "nflfastr_play_by_play",
                schema=source,
                if_exists="upsert",
                unique_keys=["game_id", "play_id"],
                chunksize=2,
            )
        subprocess.run(dbt, env=env, check=True)

        def verify(expected_yards):
            with engine.connect() as connection:
                assert (
                    connection.execute(
                        text(f'SELECT count(*) FROM "{source}".nflfastr_play_by_play')
                    ).scalar_one()
                    == 5
                )
                data = pd.read_sql(
                    text(f'SELECT * FROM "{prefix}_marts".fct_receiving_weekly'),
                    connection,
                )
            assert len(data) == 3  # Player A remains distinct across two teams.
            assert data.targets.sum() == 3  # POST and two-point attempts excluded.
            assert data.rec_yards.sum() == expected_yards
            assert sorted(data.target_share) == [0.5, 0.5, 1.0]

        verify(30)
        corrected = frame.iloc[:1].copy()
        corrected["receiving_yards"] = 20.0
        connector.publish(
            corrected,
            "nflfastr_play_by_play",
            schema=source,
            if_exists="upsert",
            unique_keys=["game_id", "play_id"],
        )
        subprocess.run(dbt, env=env, check=True)
        verify(40)
        subprocess.run([*dbt[:1], "docs", "generate", *dbt[2:]], env=env, check=True)
        print("PostgreSQL replay, correction and dbt mart checks passed.")
    finally:
        with engine.begin() as connection:
            for schema in reversed(created):
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


if __name__ == "__main__":
    main()
