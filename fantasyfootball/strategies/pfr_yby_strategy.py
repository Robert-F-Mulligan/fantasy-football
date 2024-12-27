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

    def run(self, sleep: int = 5, output_mode: str = "db") -> Optional[pd.DataFrame]:
        """
        Executes the data retrieval and transformation process for a dataset.

        :return: A concatenated DataFrame containing all processed data.    
        """
        output_method = self.output_modes.get(output_mode)
        
        years = range(self.min_year, self.max_year + 1)

        logger.info(f"Starting data processing for years {years} for {self.dataset_name} dataset.")

        with self.connector as connector:
            for ix, year in enumerate(years):
                year_df = self.run_one(year=year,
                                       connector=connector)
                if not year_df.empty:
                    output_method(year_df, append=(ix > 0))
                time.sleep(sleep)
            
            if self.all_data:
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
    pass