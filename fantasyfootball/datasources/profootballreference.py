import logging
import re
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
        return (
            self._get_data_from_html(endpoint=endpoint,
                                       table_id=table_id)
                .pipe(self._clean_columns)
        ) 

    def get_player_hrefs(self, endpoint: str, table_id: str) -> list[str]:
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

            return self._extract_player_hrefs(table_id)
        
        except Exception as e:
            logger.error(f"Error in fetching or extracting player hrefs: {e}")
            raise
    
    def _extract_player_hrefs(self, table_id: str) -> list[str]:
        """
        Helper method to extract player hrefs from a specific table in the parsed HTML content.
        
        :param table_id: The ID of the table containing player hrefs.
        :return: A list of player hrefs extracted from the content.
        """
        try:
            table = self.parser.extract(element='table', id=table_id)
            if not table:
                raise ValueError(f"Table with ID '{table_id}' not found.")

            if isinstance(table, list):
                table = table[0]

            links = table.find_all('a', href=True)
            
            pattern = re.compile(r"^/players/[A-Z]/[A-Za-z]+[0-9]{2}\.htm$")
            player_hrefs = [link.get('href') for link in links if pattern.match(link.get('href'))]

            logger.info(f"Extracted {len(player_hrefs)} player href(s) from table with ID '{table_id}'.")
            return player_hrefs

        except Exception as e:
            logger.error(f"Error in extracting player hrefs from table: {e}")
            raise

    def _player_id_transform(self, player_href: str) -> tuple[str, str]:
        """
        Transforms the player's href into the last name letter and player ID.
        
        :param player_href: The href for the player (e.g., '/players/C/CunnMa00.htm').
        :return: A tuple containing the last name letter and player ID.
        """
        last_name_letter = player_href.split('/')[2]
        player_id = player_href.split('/')[3].rsplit('.', 1)[0]
        return last_name_letter, player_id
    
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
            pos_text = next(
                (tag.get_text() for tag in self.parser.extract(element="p") if "Position" in str(tag)), 
                None
            )
            if pos_text:
                pos = pos_text.split()[1]
                return pos
            else:
                return "-"
        except IndexError:
            logger.warning("Position text found, but could not extract position.")
            return "-"
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