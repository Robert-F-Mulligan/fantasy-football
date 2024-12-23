import logging
import time
from typing import Iterable
import pandas as pd
from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.factories.strategy_factory import StrategyFactory

logger = logging.getLogger(__name__)

@StrategyFactory.register('year_by_year')
class ProFootballReferenceYbYStrategy(BaseStrategy):
    def __init__(self, combined_config: dict, **kwargs):
        super().__init__(combined_config, **kwargs)
        """
        Initializes the controller with the base URL and endpoints.
        
        :param base_url: Base URL for Pro Football Reference.
        :param endpoints: Dictionary mapping endpoint paths to table IDs.
        """
        self.all_data = []

    def run(self, sleep: int = 5):
        years = range(self.min_year, self.max_year + 1)

        logger.info(f"Starting data processing for years {years} for {self.dataset_name} dataset.")

        with self.connector as connector:
            for year in years:
                year_df = self.run_one(year=year,
                                       connector=connector)
                if not year_df.empty:
                    self.all_data.append(year_df)
                time.sleep(sleep)
            
            df = pd.concat(self.all_data, ignore_index=True) if self.all_data else pd.DataFrame()

            logger.info(f"Returning a DataFrame with shape: {df.shape}")
            return df

    def run_one(self, year: int, connector) -> pd.DataFrame:
        try:
            if not self.endpoint_template:
                raise ValueError("Endpoint template is missing.")
            
            endpoint = self.endpoint_template.format(year=year)
            additional_cols = {
                    'year': year
                    }
            
            df = (self.datasource.get_data(endpoint=endpoint, 
                                           table_id=self.table_id,
                                           connector=connector,
                                           parser=self.parser)
                      .pipe(self.datasource.assign_columns, **additional_cols)
            )
            return self.transformer.transform(dataframe=df)

        except Exception as e:
            logger.error(f"Failed to process data for year {year}: {e}")
            return pd.DataFrame()
           

if __name__ == "__main__":
    # main(start_year=2021, end_year=2023, sleep=5)
    from fantasyfootball.utils.logging_config import setup_logging

    # setup_logging()

    datasource_config = {
            "base_url": "https://www.pro-football-reference.com",
            "connector": "requests",
            "parser": "html"
        }
    dataset_config = {
            "datasource": "profootballreference",
            "table_id": "fantasy",
            "endpoint_template": "years/{year}/fantasy.htm",
            "transformer": "prf_year_by_year",
            "strategy": "year_by_year"
        }
    strat = ProFootballReferenceYbYStrategy(datasource_config=datasource_config,
                                dataset_config=dataset_config)
    
    df = strat.run(2023)
    df.to_csv("yby_test.csv", index=False)