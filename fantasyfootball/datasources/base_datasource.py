from abc import ABC,abstractmethod
from io import StringIO
import logging
import pandas as pd
from fantasyfootball.connectors.base_connector import BaseConnector
from fantasyfootball.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

class BaseDataSource(ABC):
    def __init__(self, connector: BaseConnector=None, parser: BaseParser=None):
        self.connector = connector
        self.parser = parser

    @abstractmethod
    def get_data(self, **kwargs) -> pd.DataFrame:
        """Get the final DataFrame from the data source"""
        pass

    def _get_data_from_html(self, endpoint: str, table_id: str, connector=None, parser=None) -> pd.DataFrame:
        """
        Fetches a specific table and returns it as a pandas DataFrame.
        
        :param endpoint: The endpoint to fetch the data from.
        :param table_id: The ID of the HTML table to extract.
        :return: A pandas DataFrame containing the table data.
        """
        self.connector = connector or self.connector
        self.parser = parser or self.parser

        if not self.connector or not self.parser:
            raise ValueError("Connector and parser must be provided either at init or in get_data.")
        
        try:
            logger.info(f"Fetching data from endpoint: {endpoint}")
            html_content = self.connector.fetch(endpoint)
            self.parser.set_content(html_content)
            self.parser.parse()
            table = self.parser.extract(element='table', id=table_id)

            if not table:
                raise ValueError(f"Table with ID '{table_id}' not found.")

            if isinstance(table, list):
                table = table[0]
            
            table_html = str(table)
            html_buffer = StringIO(table_html)
            df = (
                pd.read_html(html_buffer)[0]
                .pipe(self._clean_columns)
            )
            logger.info("DataFrame created successfully.")
            return df
        
        except Exception as e:
            logger.error(f"Error in fetching or parsing data: {e}")
            raise

    def _clean_columns(self, dataframe: pd.DataFrame, flatten_headers: bool = True) -> pd.DataFrame:
        """Cleans DataFrame columns."""
        logger.debug("Cleaning columns: dropping unwanted columns and flattening headers if needed.")
        if flatten_headers and hasattr(dataframe.columns, 'levels'):  # Check for multi-level columns
            dataframe.columns = ['_'.join(col) for col in dataframe.columns]

        dataframe.columns = [col.lower() for col in dataframe.columns]
        dataframe.columns = [col.split('_')[-1] if 'level' in col else col for col in dataframe.columns]
        return dataframe
    
    def assign_columns(self, dataframe: pd.DataFrame, **columns: dict) -> pd.DataFrame:
        """
        Assigns metadata to the given DataFrame by optionally including player name, position, 
        and any additional metadata passed as kwargs.
        
        :param dataframe: The DataFrame to augment with metadata.
        :param cols: Additional metadata to add as columns.
        :return: The augmented DataFrame with the new columns.
        """
        evaluated_columns = {}
        for key, value in columns.items():
            if callable(value): 
                evaluated_columns[key] = value()  # Call the method and store the result
            else:
                evaluated_columns[key] = value  # If not callable, keep the value as is
        return dataframe.assign(**evaluated_columns)
