import logging
import time
from typing import Iterable
import pandas as pd
from fantasyfootball.controllers.base_controller import BaseController
from fantasyfootball.connectors.requests_connector import RequestsConnector
from fantasyfootball.transformers.profootballreference_transformer import YearByYearTransformer
from fantasyfootball.parsers.html_parser import HTMLParser
from fantasyfootball.datasources.profootballreference import ProFootballReferenceDataSource
from fantasyfootball.utils.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

BASE_URL =  "https://www.pro-football-reference.com"

class ProFootballReferenceYbYController(BaseController):
    def __init__(self, datasource: ProFootballReferenceDataSource, transformer: YearByYearTransformer):
        """
        Initializes the controller with the base URL and endpoints.
        
        :param base_url: Base URL for Pro Football Reference.
        :param endpoints: Dictionary mapping endpoint paths to table IDs.
        """
        self.datasource = datasource
        self.transformer = transformer
        self.all_data = []

    def run(self, years: int | Iterable[int], sleep: int = 5):
        if isinstance(years, int):
            years = [years]
        for year in years:
            year_df = self.run_one(year)
            if not year_df.empty:
                self.all_data.append(year_df)
            time.sleep(sleep)
        
        return pd.concat(self.all_data, ignore_index=True) if self.all_data else pd.DataFrame()

    def run_one(self, year: int):
        try:
            endpoint = self.get_endpoint_for_year(year)
            
            df = self.datasource.get_data(endpoint=endpoint, table_id='fantasy')
            return self.transformer.transform(dataframe=df, year=year)

        except Exception as e:
            logger.error(f"Failed to process data for year {year}: {e}")
            return pd.DataFrame()
        
    def get_endpoint_for_year(self, year: int) -> str:
        """Generate the endpoint URL for a specific year."""
        return f"years/{year}/fantasy.htm" 

def main(start_year: int, end_year: int, sleep: int = 5, output_file: str = "output.csv"):
    """
    Main function to process data for a range of years and save the result to a CSV file.

    :param start_year: Starting year of the range.
    :param end_year: Ending year of the range.
    :param sleep: Time to wait (in seconds) between requests to avoid rate-limiting.
    :param output_file: Name of the file to save the output.
    """

    years = range(start_year, end_year + 1)

    connector = RequestsConnector(base_url=BASE_URL)

    with connector as conn:
        parser = HTMLParser()
        datasource = ProFootballReferenceDataSource(connector=conn, parser=parser)
        transformer = YearByYearTransformer()
        controller = ProFootballReferenceYbYController(datasource=datasource, transformer=transformer)

        try:
            logger.info(f"Starting data processing for years {start_year} to {end_year}...")
            final_df = controller.run(years=years, sleep=sleep)

            if not final_df.empty:
                final_df.to_csv(output_file, index=False)
                logger.info(f"Data successfully saved to {output_file}.")
            else:
                logger.warning("No data to save. The resulting DataFrame is empty.")
        except Exception as e:
            logger.error(f"An error occurred during processing: {e}")

if __name__ == "__main__":
    main(start_year=2021, end_year=2023, sleep=2)