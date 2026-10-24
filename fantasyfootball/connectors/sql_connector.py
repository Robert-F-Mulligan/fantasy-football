import logging
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine, URL
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

        return URL.create('postgresql+psycopg2', username=db_config['user'], password=db_config['password'], host=db_config['host'], port=int(db_config['port']), database=db_config['name'])
    
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
                raise ValueError('chunksize must be a positive integer')
            def chunks():
                with self.get_engine().connect() as connection:
                    yield from pd.read_sql(query, con=connection, params=params, chunksize=chunksize)
            return chunks()
        with self.get_engine().connect() as connection:
            return pd.read_sql(query, con=connection, params=params)

    def table_exists(self, table_name: str, schema: str = None) -> bool:
        """
        Check if the table exists in the database.
        
        :param table_name: The name of the table to check.
        :param schema: Optional schema to check within.
        :return: True if the table exists, False otherwise.
        """
        with self.get_engine().begin() as connection:
            inspector = inspect(connection)
            return inspector.has_table(table_name, schema=schema)
        
    def create_table(self, df: pd.DataFrame, table_name: str, schema: str = None):
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
                if_exists='fail',
                index=False,
                schema=schema
            )

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
            with self.get_engine().begin() as connection:
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