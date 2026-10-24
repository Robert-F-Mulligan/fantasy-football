import logging
import time
from typing import Optional
import pandas as pd
from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.factories.strategy_factory import StrategyFactory

logger = logging.getLogger(__name__)

@StrategyFactory.register('year_by_year')
class ProFootballReferenceYbYStrategy(BaseStrategy):
    def __init__(self, combined_config: dict, **kwargs):
        super().__init__(combined_config, **kwargs)
        """
        Initialize the strategy with its combined configuration.
        :param combined_config: The combined configuration for the datasource and dataset.
        :param kwargs: Additional parameters for the strategy (optional).
        """

    def iter_frames(self, connector, sleep=5):
        for year in self.years():
            yield self.run_one(year, connector)
            time.sleep(sleep)

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
            raise
           

if __name__ == "__main__":
    pass