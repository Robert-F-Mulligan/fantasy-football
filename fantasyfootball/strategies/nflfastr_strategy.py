import logging
from typing import Optional
from itertools import product
import pandas as pd
from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.factories.strategy_factory import StrategyFactory

logger = logging.getLogger(__name__)

@StrategyFactory.register("nflfastr")
class NflfastrStrategy(BaseStrategy):
    def __init__(self, combined_config: dict, **kwargs):
        super().__init__(combined_config, **kwargs)
        """
        Initializes the controller with the base URL and endpoints.
        
        :param base_url: Base URL for Pro Football Reference.
        :param endpoints: Dictionary mapping endpoint paths to table IDs.
        """

        self.all_data = []

    def run(self, save_to_csv: bool = False) -> Optional[pd.DataFrame]:
        """
        Executes the data retrieval process for a dataset.

        :param save_to_csv: Boolean flag to decide whether to save to CSV. Defaults to False.
        :return: None if saving to CSV, or a concatenated DataFrame if not.
        """
        years = range(self.min_year, self.max_year + 1)

        for year in years:
            try:
                if not self.endpoint_template:
                    raise ValueError("Endpoint template is missing.")
                
                endpoint = self.endpoint_template.format(year=year)
                logger.info(f"Processing data for year: {year} from endpoint: {endpoint}")

                raw_data = self.get_data(self.connector, endpoint)

                if hasattr(raw_data, '__iter__'):
                    for i, chunk in enumerate(raw_data):
                        logger.debug(f"Processing chunk {i + 1} for year {year}")
                        self._process_data_chunk(chunk, save_to_csv, append=(i > 0), year=year)

                else:
                    self._process_data_chunk(raw_data, save_to_csv, append=False, year=year)

            except Exception as e:
                logger.error(f"Failed to process year {year} at endpoint {endpoint}: {str(e)}")

        if save_to_csv:
            return None

        if self.all_data:
            concatenated_data = pd.concat(self.all_data, ignore_index=True)
            logger.info(f"Successfully processed dataset")
            return concatenated_data

    def _process_data_chunk(self, data, save_to_csv: bool, append: bool, **kwargs) -> None:
        """Helper method to process a single data chunk and either save to CSV or append to internal list."""
        if save_to_csv:
            args = [value for value in kwargs.values()]    
            filename = self.get_filename(*args)
            self.save_to_csv(data, filename, append)
        else:
            self.all_data.append(data)
            
    def get_data(self, connector, endpoint: str, **cols) -> pd.DataFrame:
        """
        Fetches and transforms data from the datasource.

        :param endpoint: The endpoint to fetch data from.
        :param table_id: The table ID to parse.
        :param cols: Additional columns to assign to the resulting DataFrame.
        :return: A transformed DataFrame.
        """
        logger.debug(f"Fetching data from endpoint: {endpoint}")
        chunksize = self.chunksize if hasattr(self, "chunksize") else None
        
        raw_data = self.datasource.get_data(connector=connector,
                                            endpoint=endpoint, 
                                            chunksize=chunksize)
        raw_data = raw_data.assign(**cols) if cols else raw_data
        return raw_data

    
if __name__ == "__main__":
    from fantasyfootball.utils.logging_config import setup_logging

    setup_logging()

    pass