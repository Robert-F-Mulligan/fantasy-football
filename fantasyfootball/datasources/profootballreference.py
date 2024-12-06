import logging
from io import StringIO
import pandas as pd
from fantasyfootball.connectors.requests_connector import RequestsConnector
from fantasyfootball.parsers.html_parser import HTMLParser
from fantasyfootball.datasources.base_datasource import BaseDataSource

logger = logging.getLogger(__name__)

class ProFootballReferenceDataSource(BaseDataSource):
    def __init__(self, connector: RequestsConnector, parser: HTMLParser):
        """
        Initializes the data source with a connector and a parser.
        
        :param connector: An instance of RequestsConnector for fetching data.
        :param parser: An instance of HTMLParser for parsing HTML content.
        """
        super().__init__(connector=connector, parser=parser)

    def get_data(self, endpoint: str, table_id: str) -> pd.DataFrame:
        """
        Fetches and parses a specific table into a DataFrame.
        
        :param endpoint: The endpoint to fetch
        :param table_id: The HTML ID of the table to extract
        :return: A pandas DataFrame containing the table data.
        """
        try:
            logger.info(f"Fetching data from endpoint: {endpoint}")
            html_content = self.connector.fetch(endpoint)
            self.parser.set_content(html_content)
            self.parser.parse() 
            table = self.parser.extract(element='table', id=table_id)  
            if table:
                table_html = str(table)
                html_buffer = StringIO(table_html)
                df = pd.read_html(html_buffer)[0]
                logger.info("DataFrame created successfully.")
                return df
            else:
                logger.error(f"Table with ID '{table_id}' not found.")
                raise ValueError(f"Table with ID '{table_id}' not found.")
        except Exception as e:
            logger.error(f"Error in fetching or parsing data: {e}")
            raise
