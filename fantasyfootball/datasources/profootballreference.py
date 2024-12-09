import logging
from io import StringIO
import re
import pandas as pd
from bs4 import BeautifulSoup
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
        Fetches a specific table and returns it as a pandas DataFrame.
        
        :param endpoint: The endpoint to fetch the data from.
        :param table_id: The ID of the HTML table to extract.
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

    def get_player_hrefs(self, endpoint: str) -> list[str]:
        """
        Extracts player hrefs from the parsed HTML content after setting the content.
        
        :param endpoint: The endpoint to fetch data from.
        :return: A list of hrefs that link to player pages.
        """
        try:
            logger.info(f"Fetching player hrefs from endpoint: {endpoint}")
            html_content = self.connector.fetch(endpoint)
            self.parser.set_content(html_content)
            self.parser.parse()

            return self._extract_player_hrefs()
        
        except Exception as e:
            logger.error(f"Error in fetching or extracting player hrefs: {e}")
            raise
    
    def _extract_player_hrefs(self) -> list[str]:
        """
        Helper method to extract player hrefs from the parsed HTML content.
        
        :return: A list of player hrefs extracted from the content.
        """
        pattern = re.compile(r"^/players/[A-Z]/[A-Za-z]+[0-9]{2}\.htm$")
        extracted = self.parser.extract(element='a')
        return [e.get('href') for e in extracted if e.get('href') and pattern.match(e.get('href'))]

    def _player_id_transform(self, player_href: str) -> tuple[str, str]:
        """
        Transforms the player's href into the last name letter and player ID.
        
        :param player_href: The href for the player (e.g., '/players/C/CunnMa00.htm').
        :return: A tuple containing the last name letter and player ID.
        """
        last_name_letter = player_href.split('/')[2]
        player_id = player_href.split('/')[3].rsplit('.', 1)[0]
        return last_name_letter, player_id
    
    def assign_columns(self, dataframe: pd.DataFrame, include_metadata: bool = False, **kwargs):
        """
        Assigns metadata to the given DataFrame by optionally including player name, position, 
        and any additional metadata passed as kwargs.
        
        :param dataframe: The DataFrame to augment with metadata.
        :param include_metadata: Whether to include default metadata (player_name, pos).
        :param kwargs: Additional metadata to add as columns.
        :return: The augmented DataFrame with the new columns.
        """
        cols = {
            'player_name': self._extract_player_name(),
            'pos': self._extract_player_position()
        } if include_metadata else {}

        cols = {**cols, **kwargs}
        return dataframe.assign(**cols)
    
    def _extract_player_name(self) -> str:
        """
        Extracts the player's name from the soup object.
        
        :return: The player's name as a string.
        """
        try:
            return next(
                (tag.get_text().strip() for tag in self.parser.extract(element="h1")), 
                "Unknown"
            )
        except Exception as e:
            logger.error(f"Error extracting player name: {e}")
            return "Unknown"

    def _extract_player_position(self) -> str:
        """
        Extracts the player's position from the soup object.
        
        :return: The player's position as a string.
        """
        try:
            return next(
                (tag.get_text().split(":")[1].strip() for tag in self.parser.extract(element="p") if "Position" in tag.get_text()), 
                "-"
            )
        except Exception as e:
            logger.error(f"Error extracting player position: {e}")
            return "-"


if __name__ == "__main__":
    BASE_URL =  "https://www.pro-football-reference.com"
    connector = RequestsConnector(BASE_URL)
    parser = HTMLParser()
    with connector:
        data = ProFootballReferenceDataSource(connector, parser=parser)
        #df = data.get_data(endpoint='years/2023/fantasy.htm', table_id='fantasy')
        # print(df.head())
        # print(data._get_hrefs())
        href = 'players/H/HillTy00.htm'
        df = data.get_data(endpoint=href, table_id='last5')
        print(df.head(15))
        # hrefs = data.get_player_hrefs('years/2023/fantasy.htm')
        # print(hrefs[:5])