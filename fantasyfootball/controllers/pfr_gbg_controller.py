import logging
import time
from typing import Iterable
import pandas as pd
from fantasyfootball.controllers.base_controller import BaseController
from fantasyfootball.connectors.requests_connector import RequestsConnector
from fantasyfootball.transformers.profootballreference_transformer import GameByGameTransformer
from fantasyfootball.parsers.html_parser import HTMLParser
from fantasyfootball.datasources.profootballreference import ProFootballReferenceDataSource
from fantasyfootball.utils.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

BASE_URL = "https://www.pro-football-reference.com"

class ProFootballReferenceGbGCController(BaseController):
    def __init__(self, datasource: ProFootballReferenceDataSource, transformer: GameByGameTransformer):
        """
        Initializes the controller with the data source and transformer.
        
        :param datasource: Data source instance for Pro Football Reference.
        :param transformer: Transformer instance for data processing.
        """
        self.datasource = datasource
        self.transformer = transformer

    def run(self, years: Iterable[int], max_players_per_year: int = None, sleep: int = 5) -> pd.DataFrame:
        """
        Processes data for multiple years.
        
        :param years: Iterable of years to process.
        :param max_players_per_year: Maximum number of players to process per year.
        :param sleep: Time to wait (in seconds) between years to avoid rate-limiting.
        :return: A concatenated DataFrame containing all the processed data.
        """
        all_data = []

        for year in years:
            try:
                logger.info(f"Processing year: {year}")
                year_df = self._run_one_year(year, max_players_per_year, sleep=sleep)
                if not year_df.empty:
                    all_data.append(year_df)
                time.sleep(sleep)  # Sleep between each year's processing
            except Exception as e:
                logger.error(f"Failed to process year {year}: {e}")

        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    def _run_one_year(self, year: int, max_players: int = None, sleep: int = 5) -> pd.DataFrame:
        """
        Processes data for a single year.
        
        :param year: Year to process.
        :param max_players: Maximum number of players to process.
        :return: A DataFrame containing the processed data for the year.
        """
        endpoint = self.get_endpoint_for_year(year)
        player_hrefs = self.datasource.get_player_hrefs(endpoint)

        if max_players:
            player_hrefs = player_hrefs[:max_players]
        year_data = []
        for player_href in player_hrefs:
            try:
                last_name_letter, player_id = self.datasource._player_id_transform(player_href)
                player_endpoint = self.get_endpoint_for_year_and_player(year, last_name_letter, player_id)

                additional_cols = {
                    'player_id': player_id,
                    'year': year
                    }
                player_table = (self.datasource
                                .get_data(endpoint=player_endpoint, table_id="stats")
                                .pipe(self.datasource.assign_columns, include_metadata=True, **additional_cols)
                )

                transformed_data = self.transformer.transform(dataframe=player_table)
                year_data.append(transformed_data)
                
                time.sleep(sleep)  # Sleep between processing each player
            except Exception as e:
                logger.error(f"Failed to process player {player_href} for year {year}: {e}")
        
        return pd.concat(year_data, ignore_index=True) if year_data else pd.DataFrame()

    def get_endpoint_for_year(self, year: int) -> str:
        """Generate the endpoint URL for a specific year."""
        return f"years/{year}/fantasy.htm"
    
    def get_endpoint_for_year_and_player(self, year: int, last_name_letter: str, player_id: str) -> str:
        return f'/players/{last_name_letter}/{player_id}/gamelog/{year}/'
    
def main(start_year: int, end_year: int, max_players: int = None, sleep: int = 5, output_file: str = "output.csv"):
    """
    Main function to process data for a range of years and save the result to a CSV file.

    :param start_year: Starting year of the range.
    :param end_year: Ending year of the range.
    :param max_players: Maximum number of players to process per year.
    :param sleep: Time to wait (in seconds) between years to avoid rate-limiting.
    :param output_file: Name of the file to save the output.
    """
    years = range(start_year, end_year + 1)

    connector = RequestsConnector(base_url=BASE_URL)

    with connector as conn:
        parser = HTMLParser()
        datasource = ProFootballReferenceDataSource(connector=conn, parser=parser)
        transformer = GameByGameTransformer()
        controller = ProFootballReferenceGbGCController(datasource=datasource, transformer=transformer)

        try:
            logger.info(f"Starting data processing for years {start_year} to {end_year}...")
            final_df = controller.run(years=years, max_players_per_year=max_players, sleep=sleep)

            if not final_df.empty:
                final_df.to_csv(output_file, index=False)
                logger.info(f"Data successfully saved to {output_file}.")
            else:
                logger.warning("No data to save. The resulting DataFrame is empty.")
        except Exception as e:
            logger.error(f"An error occurred during processing: {e}")

if __name__ == "__main__":
    main(start_year=2022, end_year=2023, max_players=10, sleep=10)
