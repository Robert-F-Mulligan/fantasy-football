import logging
from typing import Optional
from itertools import product
import pandas as pd
from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.factories.strategy_factory import StrategyFactory

logger = logging.getLogger(__name__)

@StrategyFactory.register("fantasypros")
class FantasyProsStrategy(BaseStrategy):
    def __init__(self, combined_config: dict, **kwargs):
        super().__init__(combined_config, **kwargs)
        """
        Initializes the controller with the base URL and endpoints.
        
        :param base_url: Base URL for Pro Football Reference.
        :param endpoints: Dictionary mapping endpoint paths to table IDs.
        """

    def run(self, output_mode: str = "db") -> Optional[pd.DataFrame]:
        """
        Executes the data retrieval and transformation process for a dataset.

        :return: A concatenated DataFrame containing all processed data.
        """
        output_method = self.output_modes.get(output_mode)

        with self.connector as connector:
            positions = self.positions if hasattr(self, "positions") else [None]
            week = self.week if hasattr(self, "week") else [None]

            logger.info(f"Starting data processing for {self.dataset_name} dataset.")
            logger.info(f"Positions: {positions}")
            logger.info(f"Week: {week}")
            
            for ix, (pos, week) in enumerate(product(positions, week)):
                    try:
                        if not self.endpoint_template:
                            raise ValueError("Endpoint template is missing.")
                        endpoint = self.endpoint_template.format(position=pos or "", week=week or "")

                        cols = {
                                "pos": pos.upper() if pos else None,
                                "week": week if week else None,
                            }
                        cols = {key: value for key, value in cols.items() if value is not None}

                        data = self.get_data(connector,
                                             endpoint, 
                                             self.table_id, 
                                             **cols)
                        if not data.empty:
                            output_method(data, append=(ix > 0))
                    except Exception as e:
                        logger.error(f"Failed to process position {pos} at endpoint {endpoint}: {e}")
    
            if self.all_data:
                concatenated_data = pd.concat(self.all_data, ignore_index=True)
                logger.debug(f"Data processed in {output_mode} mode.")
                return concatenated_data
            
    def get_data(self, connector, endpoint: str, table_id: str, **cols) -> pd.DataFrame:
        """
        Fetches and transforms data from the datasource.

        :param endpoint: The endpoint to fetch data from.
        :param table_id: The table ID to parse.
        :param cols: Additional columns to assign to the resulting DataFrame.
        :return: A transformed DataFrame.
        """
        logger.debug(f"Fetching data from endpoint: {endpoint}")
        
        raw_data = self.datasource.get_data(connector=connector,
                                            endpoint=endpoint, 
                                            table_id=table_id,
                                            parser=self.parser)
        raw_data = raw_data.assign(**cols) if cols else raw_data
        
        transformed_data = self.transformer.transform(raw_data)
        logger.info(f"Transformed data successfully")
        return transformed_data

    
if __name__ == "__main__":
    from fantasyfootball.utils.logging_config import setup_logging

    setup_logging()

    datasource_config = {
            "base_url": "https://www.fantasypros.com",
            "connector": "selenium",
            "parser": "html",
            "datasource": "fantasypros",
            "table_id": "ranking-table",
            "endpoint_template": "nfl/rankings/ppr-cheatsheets.php",
            "transformer": "fantasy_pros_draft",
            "strategy": "fantasypros",
            "dataset_name": "fantasy_pros_draft"
        }
    dataset_config = {
            
        }
    strat = FantasyProsStrategy(datasource_config)
    
    df = strat.run(output_mode='db')

