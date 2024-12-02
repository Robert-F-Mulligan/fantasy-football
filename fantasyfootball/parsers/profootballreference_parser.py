import logging
from base_parser import BaseParser
import pandas as pd
from bs4 import BeautifulSoup
from base_parser import BaseParser
from fantasyfootball.connectors.requests_connector import RequestsConnector

logger = logging.getLogger(__name__)


class PFRGbgParser(BaseParser):
    def __init__(self, soup: BeautifulSoup):
        super().__init__(soup)

    def validate_soup(self):
        """Ensure the soup contains necessary elements."""
        if not self.soup.find("table"):
            raise ValueError("HTML does not contain a table")
        logger.info("Soup validated successfully.")

    def parse(self) -> pd.DataFrame:
        """Parse the soup and return the player's game data as a DataFrame."""
        df = self._extract_table(self.soup)
        df = self._transform_table(df)
        return df

    def process_year(self, year: int, connector: RequestsConnector, max_players: int = 300) -> pd.DataFrame:
        """Process all players for the given year."""
        hrefs = self.get_player_hrefs(year, connector)
        dfs = (
            self.process_player(href, year, connector) for href in hrefs[:max_players]
        )
        return pd.concat(dfs, ignore_index=True)

    def get_player_hrefs(self, year: int, connector: RequestsConnector) -> list:
        """Get player hrefs for a specific year."""
        html = connector.fetch("fantasy", params={"year": year})
        soup = BeautifulSoup(html, "html.parser")
        return [a["href"] for a in soup.find_all("a", href=True) if "players" in a["href"]]

    def process_player(self, href: str, year: int, connector: RequestsConnector) -> pd.DataFrame:
        """Process a single player, fetching their game logs."""
        player_id = href.split("/")[3]
        soup = connector.get_data(f"players/{player_id}/gamelog/{year}")
        player_parser = PFRGbgParser(soup)
        return player_parser.parse()
