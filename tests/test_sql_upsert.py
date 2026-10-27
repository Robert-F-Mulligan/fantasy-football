"""The same correction/rollback contract on SQLite and CI PostgreSQL."""

import os
from uuid import uuid4

import pandas as pd
import pytest
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.exc import IntegrityError

from fantasyfootball.connectors.sql_connector import SqlConnector


@pytest.fixture(params=["sqlite", "postgresql"])
def store(request, tmp_path):
    url = (
        os.getenv("TEST_DATABASE_URL")
        if request.param == "postgresql"
        else f"sqlite:///{tmp_path / 'test.db'}"
    )
    if not url:
        pytest.skip("PostgreSQL integration requires TEST_DATABASE_URL")
    connector = SqlConnector()
    connector.engine = create_engine(url)
    table = Table(
        "upsert_" + uuid4().hex,
        MetaData(),
        Column("season", Integer, nullable=False),
        Column("player", String, nullable=False),
        Column("points", Integer, nullable=False, server_default="0"),
        Column("note", String, server_default="retained"),
        UniqueConstraint("season", "player"),
    )
    table.create(connector.engine)
    yield connector, table
    table.drop(connector.engine)
    connector.engine.dispose()


def publish(store, rows, **kwargs):
    connector, table = store
    connector.publish(
        pd.DataFrame(rows),
        table.name,
        if_exists="upsert",
        unique_keys=["season", "player"],
        **kwargs,
    )


def rows(store):
    connector, table = store
    with connector.engine.connect() as connection:
        return [
            dict(r)
            for r in connection.execute(
                select(table).order_by(table.c.player)
            ).mappings()
        ]


def test_replay_correction_partial_update_and_keys_only(store):
    batch = [
        {"season": 2026, "player": "a", "points": 10},
        {"season": 2026, "player": "b", "points": 5},
    ]
    publish(store, batch, chunksize=1)
    publish(store, batch, chunksize=1)
    publish(store, [{"player": "a", "points": 12, "season": 2026}])
    publish(store, [{"player": "a", "season": 2026}])
    assert rows(store) == [
        {"season": 2026, "player": "a", "points": 12, "note": "retained"},
        {"season": 2026, "player": "b", "points": 5, "note": "retained"},
    ]


@pytest.mark.parametrize(
    "bad",
    [
        [{"season": 2026, "player": None, "points": 2}],
        [{"season": 2026, "player": "a", "points": 2}] * 2,
        [{"season": 2026, "points": 2}],
    ],
)
def test_invalid_keys_leave_destination_unchanged(store, bad):
    publish(store, [{"season": 2026, "player": "a", "points": 10}])
    with pytest.raises(ValueError):
        publish(store, bad)
    assert rows(store)[0]["points"] == 10


def test_failure_in_later_chunk_rolls_back_correction(store):
    publish(store, [{"season": 2026, "player": "a", "points": 10}])
    with pytest.raises(IntegrityError):
        publish(
            store,
            [
                {"season": 2026, "player": "a", "points": 12},
                {"season": 2026, "player": "b", "points": None},
            ],
            chunksize=1,
        )
    assert len(rows(store)) == 1
    assert rows(store)[0]["points"] == 10


def test_wrong_conflict_key_rejected(store):
    connector, table = store
    with pytest.raises(ValueError, match="constraint"):
        connector.publish(
            pd.DataFrame([{"season": 2026, "player": "a", "points": 1}]),
            table.name,
            if_exists="upsert",
            unique_keys=["player"],
        )


def test_strategy_keeps_upsert_across_frames():
    from unittest.mock import Mock

    from fantasyfootball.strategies.nflfastr_strategy import NflfastrStrategy

    strategy = NflfastrStrategy(
        {
            "dataset_name": "plays",
            "if_exists": "upsert",
            "unique_keys": ["game_id", "play_id"],
        }
    )
    strategy.sql_connector = Mock()
    frame = pd.DataFrame({"game_id": ["g"], "play_id": [1]})
    strategy.publish_to_database(frame)
    strategy.publish_to_database(frame, append=True)
    assert all(
        c.kwargs["if_exists"] == "upsert"
        and c.kwargs["unique_keys"] == ["game_id", "play_id"]
        for c in strategy.sql_connector.publish.call_args_list
    )
