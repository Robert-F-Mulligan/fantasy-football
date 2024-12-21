import logging
import time
from typing import Iterable
import pandas as pd
from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.connectors.requests_connector import RequestsConnector
from fantasyfootball.transformers.profootballreference_transformer import YearByYearTransformer
from fantasyfootball.parsers.html_parser import HTMLParser
from fantasyfootball.datasources.profootballreference import ProFootballReferenceDataSource
from fantasyfootball.factories.strategy_factory import StrategyFactory
import fantasyfootball.connectors # register connectors
from fantasyfootball.factories.connector_factory import ConnectorFactory
import fantasyfootball.datasources # register datasources
from fantasyfootball.factories.datasource_factory import DatasourceFactory
import fantasyfootball.transformers # register transformers
from fantasyfootball.factories.transformer_factory import TransformerFactory
import fantasyfootball.parsers # register parsers
from fantasyfootball.factories.parser_factory import ParserFactory

logger = logging.getLogger(__name__)

@StrategyFactory.register('year_by_year')
class ProFootballReferenceYbYStrategy(BaseStrategy):
    def __init__(self, datasource_config: dict, dataset_config: dict):
        """
        Initializes the controller with the base URL and endpoints.
        
        :param base_url: Base URL for Pro Football Reference.
        :param endpoints: Dictionary mapping endpoint paths to table IDs.
        """
        self.datasource_config = datasource_config
        self.dataset_config = dataset_config
        self.all_data = []

    def run(self, years: int | Iterable[int], sleep: int = 5):
        if isinstance(years, int):
            years = [years]

        self.parse_config()

        logger.info(f"Starting data processing for years {years}...")

        with self.connector as connector:
            self.datasource = DatasourceFactory.create(self.dataset_config['datasource'],
                                                       connector=connector, 
                                                       parser=self.parser)

            for year in years:
                year_df = self.run_one(year)
                if not year_df.empty:
                    self.all_data.append(year_df)
                time.sleep(sleep)
            
            df = pd.concat(self.all_data, ignore_index=True) if self.all_data else pd.DataFrame()

            logger.info(f"Returning a DataFrame with shape: {df.shape}")
            return df

    def run_one(self, year: int):
        try:
            endpoint = self.endpoint_template.format(year=year)
            additional_cols = {
                    'year': year
                    }
            
            df = (self.datasource.get_data(endpoint=endpoint, table_id=self.table_id)
                      .pipe(self.datasource.assign_columns, **additional_cols)
            )
            return self.transformer.transform(dataframe=df)

        except Exception as e:
            logger.error(f"Failed to process data for year {year}: {e}")
            return pd.DataFrame()
        
    def get_endpoint_for_year(self, year: int) -> str:
        """Generate the endpoint URL for a specific year."""
        return f"years/{year}/fantasy.htm"
    
    def parse_config(self) -> None:
        """
        Parses the configuration for a specific dataset.

        :raises ValueError: If the dataset name is not in the configuration.
        """
        # datasource configuration
        self.base_url = self.datasource_config['base_url']
        self.connector = ConnectorFactory.create(self.datasource_config['connector'],
                                                 base_url=self.base_url)
        self.parser = ParserFactory.create(self.datasource_config['parser'])
        
        # dataset configuration
        self.transformer = TransformerFactory.create(self.dataset_config['transformer'])
        self.table_id = self.dataset_config['table_id']
        self.endpoint_template = self.dataset_config['endpoint_template']
        logger.info(f"Parsed configuration for dataset")

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