import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import pandas as pd
from fantasyfootball.connectors.base_connector import BaseConnector
from fantasyfootball.factories.connector_factory import ConnectorFactory
from fantasyfootball.utils.retry_decorator import retry_decorator

logger = logging.getLogger(__name__)

@ConnectorFactory.register("sql")
class SqlConnector(BaseConnector):
    def __init__(self):
        """
        Initialize the connector.
        """
        self.engine = None

    def construct_url(self) -> str:
        """Combine base_url with endpoint."""
        db_config = {
            'host': os.getenv('DB_HOST'),
            'port': os.getenv('DB_PORT'),
            'name': os.getenv('DB_NAME'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
        }

        if not all(db_config.values()):
            raise ValueError("One or more environment variables are missing!")

        return "postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}".format(**db_config)
    
    def get_engine(self) -> Engine:
        """Lazily initialize the SQLAlchemy engine."""
        if self.engine is None:
            db_url = self.construct_url()
            logger.info("Creating SQLAlchemy engine.")
            self.engine = create_engine(db_url, pool_pre_ping=True)
        return self.engine

    @retry_decorator(retries=3, delay=2, backoff_factor=2)
    def fetch(self, query: str, params: dict = None, chunksize: int = None) -> pd.DataFrame:
        """
        Execute a SELECT query and fetch results into a Pandas DataFrame.
        
        :param query: SQL query to execute.
        :param params: Parameters for the query.
        :param chunksize: Number of rows to fetch per chunk.
        :return: Query results as a Pandas DataFrame (or generator if chunksize is set).
        """
        logger.info("Executing fetch query.")
        try:
            with self.get_engine().connect() as connection:
                logger.debug(f"Running query: {query} with params: {params}")
                return pd.read_sql(query, con=connection, params=params, chunksize=chunksize)
        except Exception as e:
            logger.error(f"Error fetching data: {e}", exc_info=True)
            raise

    @retry_decorator(retries=3, delay=2, backoff_factor=2)
    def publish(self, df: pd.DataFrame, table_name: str, if_exists: str = 'append', chunksize: int = None, schema: str = None):
        """
        Publish a DataFrame to a SQL table using pandas `to_sql`.
        
        :param df: DataFrame to publish.
        :param table_name: Name of the target SQL table.
        :param if_exists: What to do if the table exists ('fail', 'replace', 'append'). Default is 'append'.
        :param chunksize: Number of rows to write per chunk.
        :param schema: Optional schema name for the table.
        """
        logger.info(f"Publishing DataFrame to table {table_name}.")
        try:
            with self.get_engine().connect() as connection:
                df.to_sql(
                    name=table_name,
                    con=connection,
                    if_exists=if_exists,
                    index=False,
                    chunksize=chunksize,
                    schema=schema
                )
                logger.info(f"DataFrame successfully published to table {table_name}.")
        except Exception as e:
            logger.error(f"Error publishing data: {e}", exc_info=True)
            raise

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
    'id': [1, 2, 3, 4],
    'name': ['Alice', 'Bob', 'Charlie', 'David'],
    'age': [25, 30, 35, 40]
}

    conn = SqlConnector()
    conn.publish(df=pd.DataFrame(data), table_name='test_table')