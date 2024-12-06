import logging
import time
import pandas as pd
from fantasyfootball.controllers.base_controller import BaseController
from fantasyfootball.connectors.requests_connector import RequestsConnector
from fantasyfootball.transformers.prf_yby_transformer import YearByYearTransformer
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

    def run(self, year: int):
        try:
            endpoint = self.get_endpoint_for_year(year)
            
            df = self.datasource.get_data(endpoint=endpoint, table_id='fantasy')
            return self.transformer.transform(df=df, year=year)

        except Exception as e:
            logger.error(f"Failed to process data for year {year}: {e}")
            return pd.DataFrame() 

    def get_endpoint_for_year(self, year: int) -> str:
        """Generate the endpoint URL for a specific year."""
        return f"years/{year}/fantasy.htm" 

def main(sleep: int = 5):
    start_year = 2022
    end_year = 2024

    connector = RequestsConnector(base_url="https://www.pro-football-reference.com")
    with connector as conn:
        parser = HTMLParser()
        datasource = ProFootballReferenceDataSource(connector=conn, parser=parser)
        transformer = YearByYearTransformer()      

        all_data = []  # List to collect DataFrames

        controller = ProFootballReferenceYbYController(datasource=datasource, transformer=transformer)

        for year in range(start_year, end_year + 1):
            print(f"Processing data for year {year}...")
            year_df = controller.run(year)
            if not year_df.empty:
                all_data.append(year_df)
            time.sleep(sleep)

        # Concatenate all the DataFrames from different years
        final_df = pd.concat(all_data, ignore_index=True)

        final_df.to_csv("combined_output.csv", index=False)
        print("Data saved to combined_output.csv.")

        print(final_df.head())  # Display the final DataFrame

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    main()