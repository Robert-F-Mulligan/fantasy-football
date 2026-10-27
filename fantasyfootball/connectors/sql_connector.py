import logging
import os

import pandas as pd
from sqlalchemy import MetaData, Table, create_engine, inspect
from sqlalchemy.engine import URL, Engine

from fantasyfootball.connectors.base_connector import BaseConnector
from fantasyfootball.factories.connector_factory import ConnectorFactory

logger = logging.getLogger(__name__)


@ConnectorFactory.register("sql")
class SqlConnector(BaseConnector):
    def __init__(self):
        """
        Initialize the connector.
        """
        self.engine = None

    def construct_url(self) -> URL:
        """Combine base_url with endpoint."""
        db_config = {
            "host": os.getenv("DB_HOST"),
            "port": os.getenv("DB_PORT"),
            "name": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
        }

        if not all(db_config.values()):
            raise ValueError("One or more environment variables are missing!")

        return URL.create(
            "postgresql+psycopg2",
            username=db_config["user"],
            password=db_config["password"],
            host=db_config["host"],
            port=int(db_config["port"]),
            database=db_config["name"],
        )

    def get_engine(self) -> Engine:
        """Lazily initialize the SQLAlchemy engine."""
        if self.engine is None:
            db_url = self.construct_url()
            logger.info("Creating SQLAlchemy engine.")
            self.engine = create_engine(db_url, pool_pre_ping=True)
        return self.engine

    def fetch(self, query: str, params=None, chunksize=None):
        """Keep the SQL connection alive until a chunk iterator is exhausted."""
        if chunksize is not None:
            if not isinstance(chunksize, int) or chunksize < 1:
                raise ValueError("chunksize must be a positive integer")

            def chunks():
                with self.get_engine().connect() as connection:
                    yield from pd.read_sql(
                        query, con=connection, params=params, chunksize=chunksize
                    )

            return chunks()
        with self.get_engine().connect() as connection:
            return pd.read_sql(query, con=connection, params=params)

    def table_exists(self, table_name: str, schema: str | None = None) -> bool:
        """
        Check if the table exists in the database.

        :param table_name: The name of the table to check.
        :param schema: Optional schema to check within.
        :return: True if the table exists, False otherwise.
        """
        with self.get_engine().begin() as connection:
            inspector = inspect(connection)
            return inspector.has_table(table_name, schema=schema)

    def create_table(
        self, df: pd.DataFrame, table_name: str, schema: str | None = None
    ):
        """
        Create the table in the database based on the DataFrame schema if it does not exist.

        :param df: The DataFrame used to define the table schema.
        :param table_name: The name of the table to create.
        :param schema: Optional schema for the table.
        """
        logger.info(f"Creating table {table_name} based on DataFrame schema.")
        with self.get_engine().begin() as connection:
            df.head(0).to_sql(
                name=table_name,
                con=connection,
                if_exists="fail",
                index=False,
                schema=schema,
            )

    def publish(
        self,
        df: pd.DataFrame,
        table_name: str,
        if_exists: str = "append",
        chunksize: int | None = None,
        schema: str | None = None,
        unique_keys=None,
    ):
        """
        Publish a DataFrame to a SQL table using pandas `to_sql`.

        :param df: DataFrame to publish.
        :param table_name: Name of the target SQL table.
        :param if_exists: What to do if the table exists ('fail', 'replace', 'append'). Default is 'append'.
        :param chunksize: Number of rows to write per chunk.
        :param schema: Optional schema name for the table.
        """
        if if_exists == "upsert":
            return self.upsert(
                df, table_name, unique_keys, schema=schema, chunksize=chunksize
            )
        if unique_keys is not None:
            raise ValueError("unique_keys requires if_exists='upsert'")
        logger.info(f"Publishing DataFrame to table {table_name}.")

        try:
            with self.get_engine().begin() as connection:
                df.to_sql(
                    name=table_name,
                    con=connection,
                    if_exists=if_exists,
                    index=False,
                    chunksize=chunksize,
                    schema=schema,
                )
                logger.info(f"DataFrame successfully published to table {table_name}.")
        except Exception:
            logger.exception("Error publishing data")
            raise

    def upsert(self, df, table_name, unique_keys, *, schema=None, chunksize=None):
        """Atomically insert/correct a batch using a provisioned unique key.

        Tables and constraints must be created explicitly by a migration. Only
        supplied non-key columns are updated; rows absent from the batch remain.
        """
        if not isinstance(unique_keys, (list, tuple)) or not unique_keys:
            raise ValueError("upsert requires a nonempty list of unique_keys")
        keys = list(unique_keys)
        if not all(isinstance(k, str) for k in keys) or len(set(keys)) != len(keys):
            raise ValueError("unique_keys must be distinct column names")
        if df.columns.has_duplicates or not set(keys).issubset(df.columns):
            raise ValueError("Missing keys or duplicate frame columns")
        if df[keys].isna().any().any() or df.duplicated(keys).any():
            raise ValueError("Null or duplicate keys in upsert batch")
        if chunksize is not None and (type(chunksize) is not int or chunksize < 1):
            raise ValueError("chunksize must be a positive integer")
        engine = self.get_engine()
        if engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif engine.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise ValueError("upsert supports PostgreSQL and SQLite only")
        with engine.begin() as connection:
            inspector = inspect(connection)
            if not inspector.has_table(table_name, schema=schema):
                raise ValueError(
                    "Provision the upsert table and unique constraint first"
                )
            table = Table(
                table_name, MetaData(), schema=schema, autoload_with=connection
            )
            candidates = [inspector.get_pk_constraint(table_name, schema=schema)]
            candidates += inspector.get_unique_constraints(table_name, schema=schema)
            candidates += [
                i
                for i in inspector.get_indexes(table_name, schema=schema)
                if i.get("unique") and not i.get("dialect_options")
            ]
            if not any(
                set(c.get("constrained_columns", c.get("column_names", [])) or [])
                == set(keys)
                for c in candidates
            ):
                raise ValueError(
                    "unique_keys must match a primary key or full unique constraint"
                )
            if not set(df.columns).issubset(table.c.keys()):
                raise ValueError("Frame columns not present in destination table")
            records = df.astype(object).where(pd.notna(df), None).to_dict("records")
            size = chunksize or 1000
            for offset in range(0, len(records), size):
                statement = insert(table).values(records[offset : offset + size])
                updates = {
                    c: statement.excluded[c] for c in df.columns if c not in keys
                }
                if updates:
                    statement = statement.on_conflict_do_update(
                        index_elements=keys, set_=updates
                    )
                else:
                    statement = statement.on_conflict_do_nothing(index_elements=keys)
                connection.execute(statement)

    def __enter__(self):
        """Enter the context, initializing the engine if not already done."""
        logger.info("Entering SqlConnector context.")
        self.get_engine()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the context, disposing of the engine."""
        if self.engine:
            logger.info("Disposing SQLAlchemy engine.")
            self.engine.dispose()
            self.engine = None


if __name__ == "__main__":
    data = {
        "id": [1, 2, 3, 4],
        "name": ["Alice", "Bob", "Charlie", "David"],
        "age": [25, 30, 35, 40],
    }

    conn = SqlConnector()
    conn.publish(df=pd.DataFrame(data), table_name="test_table")
