from contextlib import contextmanager
import pandas as pd
import pytest
from fantasyfootball.factories.strategy_factory import StrategyFactory
from fantasyfootball.facade.data_facade import DataFacade, load_config
from fantasyfootball.strategies.nflfastr_strategy import NflfastrStrategy
from fantasyfootball.connectors.sql_connector import SqlConnector
from sqlalchemy import create_engine, text


def strategy(chunked=False):
    instance = NflfastrStrategy(
        {
            "min_year": 2022,
            "max_year": 2023,
            "endpoint_template": "{year}",
            "dataset_name": "test",
        }
    )

    class Source:
        def get_data(self, connector, endpoint, **kwargs):
            frame = pd.DataFrame({"year": [int(endpoint)] * 2, "value": [1, 2]})
            return iter([frame.iloc[:1], frame.iloc[1:]]) if chunked else frame

    class Transform:
        def transform(self, frame):
            return frame

    instance.datasource, instance.transformer = Source(), Transform()
    return instance


@pytest.mark.parametrize("chunked", [False, True])
def test_all_years_and_chunks_retained(chunked):
    instance = strategy(chunked)
    for _ in range(2):
        result = instance.run()
        assert result.year.tolist() == [2022, 2022, 2023, 2023]
        assert result.value.tolist() == [1, 2, 1, 2]


def test_csv_not_overwritten_at_year_boundary(tmp_path):
    instance = strategy(True)
    destination = tmp_path / "nested" / "test.csv"
    instance.combined_config["output_path"] = destination
    instance.run(output_mode="csv")
    assert len(pd.read_csv(destination)) == 4
    instance.run(output_mode="csv")
    assert len(pd.read_csv(destination)) == 4


def test_bad_output_mode_fails_before_fetch():
    with pytest.raises(ValueError, match="output mode"):
        strategy().run("typo")


def test_failures_propagate_and_close_connection():
    instance = strategy()
    closed = []

    @contextmanager
    def connection():
        try:
            yield object()
        finally:
            closed.append(True)

    class Broken:
        def transform(self, data):
            raise RuntimeError("bad schema")

    instance.connector = connection()
    instance.transformer = Broken()
    with pytest.raises(RuntimeError, match="bad schema"):
        instance.run()
    assert closed == [True]


def test_lazy_factories_build_every_configured_strategy():
    config = load_config()
    for name, dataset in config["datasets"].items():
        combined = {
            **config["datasources"][dataset["datasource"]],
            **dataset,
            "dataset_name": name,
        }
        instance = StrategyFactory.create(dataset["strategy"], combined_config=combined)
        assert instance.sql_connector is None


def test_sql_writes_commit(tmp_path):
    connector = SqlConnector()
    connector.engine = create_engine(f"sqlite:///{tmp_path / 'data.db'}")
    connector.publish(pd.DataFrame({"value": [1, 2]}), "points")
    with connector.engine.connect() as connection:
        assert connection.execute(text("select count(*) from points")).scalar() == 2
    connector.engine.dispose()


def test_sql_credentials_are_escaped(monkeypatch):
    for key, value in {
        "HOST": "localhost",
        "PORT": "5432",
        "NAME": "ff",
        "USER": "user",
        "PASSWORD": "a@:/#",
    }.items():
        monkeypatch.setenv("DB_" + key, value)
    assert SqlConnector().construct_url().password == "a@:/#"


def test_facade_bad_dataset_clear_error():
    with pytest.raises(ValueError, match="Invalid dataset"):
        DataFacade(load_config()).get_data("missing")


def test_retry_raises_original_failure_without_final_sleep(monkeypatch):
    from fantasyfootball.utils.retry_decorator import retry_decorator

    sleeps, attempts = [], []
    monkeypatch.setattr(
        "fantasyfootball.utils.retry_decorator.time.sleep", sleeps.append
    )

    @retry_decorator(retries=2, delay=1)
    def broken():
        attempts.append(1)
        raise RuntimeError("offline")

    with pytest.raises(RuntimeError, match="offline"):
        broken()
    assert len(attempts) == 3
    assert sleeps == [1, 2]


def test_sql_chunk_read(tmp_path):
    connector = SqlConnector()
    connector.engine = create_engine(f"sqlite:///{tmp_path / 'chunks.db'}")
    connector.publish(pd.DataFrame({"value": [1, 2, 3]}), "points")
    frames = list(connector.fetch("select * from points", chunksize=2))
    assert [len(frame) for frame in frames] == [2, 1]
    assert pd.concat(frames).value.tolist() == [1, 2, 3]
    connector.engine.dispose()
