import logging
import time
from typing import Optional
import pandas as pd
from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.factories.strategy_factory import StrategyFactory
from fantasyfootball.utils.logging_config import setup_logging


logger = logging.getLogger(__name__)

@StrategyFactory.register('game_by_game')
class ProFootballReferenceGbGStrategy(BaseStrategy):
    def __init__(self, combined_config: dict, **kwargs):
        super().__init__(combined_config, **kwargs)
        """
        Initialize the strategy with its combined configuration.
        :param combined_config: The combined configuration for the datasource and dataset.
        :param kwargs: Additional parameters for the strategy (optional).
        """
        self.all_data = []

    def iter_frames(self, connector, sleep=5):
        for year in self.years():
            yield self._run_one_year(year, sleep=sleep, connector=connector, parser=self.parser)
            time.sleep(sleep)

    def _run_one_year(self, year: int, sleep: int = 5, **kwargs) -> pd.DataFrame:
        """
        Processes data for a single year.
        
        :param year: Year to process.
        :param max_players: Maximum number of players to process.
        :return: A DataFrame containing the processed data for the year.
        """
        endpoint = self.year_endpoint_template.format(year=year)
        player_hrefs = self.datasource.get_player_hrefs(endpoint, 
                                                        table_id=self.href_table_id,
                                                        **kwargs)

        if getattr(self, 'max_players_per_year', None):
            player_hrefs = player_hrefs[:self.max_players_per_year]

        year_data = []
        for player_href in player_hrefs:
            try:
                last_name_letter, player_id = self.datasource._player_id_transform(player_href)
                player_endpoint = self.endpoint_template.format(year=year, 
                                                                last_name_letter=last_name_letter,
                                                                player_id=player_id)

                additional_cols = {
                    'player_id': player_id,
                    'year': year,
                    'player_name': self.datasource._extract_player_name,
                    'pos': self.datasource._extract_player_position
                }

                player_table = (self.datasource
                                .get_data(endpoint=player_endpoint, 
                                          table_id=self.table_id,
                                          **kwargs)
                                .pipe(self.datasource.assign_columns, **additional_cols)
                )
                logger.debug(f"Constructed player endpoint: {player_endpoint}")
                logger.debug(f"Columns added: {additional_cols}")

                transformed_data = self.transformer.transform(dataframe=player_table)
                year_data.append(transformed_data)
                
                time.sleep(sleep)  # Sleep between processing each player
            except Exception as e:
                logger.error(f"Failed to process player {player_href} for year {year}: {e}")
                raise
        
        return pd.concat(year_data, ignore_index=True) if year_data else pd.DataFrame()


if __name__ == "__main__":
    pass
