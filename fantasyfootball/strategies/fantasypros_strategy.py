import logging
from typing import Optional
import pandas as pd
from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.connectors.selenium_connector import SeleniumConnector
from fantasyfootball.transformers.fantasypros_transformer import ProjectionsTransfomer, RankingsTransfomer, DraftTransfomer
from fantasyfootball.parsers.html_parser import HTMLParser
from fantasyfootball.datasources.fantasypros import FantasyProsDatasource
from fantasyfootball.factories.strategy_factory import StrategyFactory
from fantasyfootball.utils.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

BASE_URL =  "https://www.fantasypros.com"
DRIVER_PATH = r'C:\Users\rmull\python-projects\fantasy-football\chrome-driver\chromedriver.exe'

FANTASY_PROS_CONFIG = {
    'projections': {
        'table_id': 'data',
        'endpoint_template': 'nfl/projections/{position}.php?week=draft&scoring=PPR&week={week}',
        'transformer': ProjectionsTransfomer,
        'positions': ['QB', 'RB', 'WR', 'TE'] 
    },
    'weekly_rank': {
        'table_id': 'ranking-table',
        'endpoint_template': 'nfl/rankings/ppr-{position}.php',
        'transformer': RankingsTransfomer,
        'positions': ['QB', 'RB', 'WR', 'TE'] 
    },
    'draft': {
        'table_id': 'ranking-table',
        'endpoint_template': 'nfl/rankings/ppr-cheatsheets.php',
        'transformer': DraftTransfomer,
        'positions': None  # No iteration required
    }
}

@StrategyFactory.register('fantasypros')
class FantasyProsStrategy(BaseStrategy):
    def __init__(self, datasource: FantasyProsDatasource):
        """
        Initializes the controller with the base URL and endpoints.
        
        :param base_url: Base URL for Pro Football Reference.
        :param endpoints: Dictionary mapping endpoint paths to table IDs.
        """
        self.datasource = datasource
        self.all_data = []

    def run(self, dataset_name: str, week: Optional[int] = None) -> pd.DataFrame:
        """
        Executes the data retrieval and transformation process for a dataset.

        :param dataset_name: The name of the dataset to process.
        :param week: Optional week number for weekly datasets.
        :return: A concatenated DataFrame containing all processed data.
        """
        self.parse_config(dataset_name)

        all_data = []
        if self.positions:
            for pos in self.positions:
                try:
                    logger.info(f"Processing position: {pos}")
                    endpoint = self.endpoint_template.format(position=pos, week=week)
                    data = self.get_data(endpoint, self.table_id, position=pos)
                    if not data.empty:
                        all_data.append(data)
                except Exception as e:
                    logger.error(f"Failed to process position {pos}: {e}")
        else:
            endpoint = self.endpoint_template
            data = self.get_data(endpoint, self.table_id)
            if not data.empty:
                all_data.append(data)

        if all_data:
            concatenated_data = pd.concat(all_data, ignore_index=True)
            logger.info(f"Successfully processed dataset: {dataset_name}")
            return concatenated_data
        else:
            logger.warning(f"No data collected for dataset: {dataset_name}")
            return pd.DataFrame()
            
    def get_data(self, endpoint: str, table_id: str, **cols) -> pd.DataFrame:
        """
        Fetches and transforms data from the datasource.

        :param endpoint: The endpoint to fetch data from.
        :param table_id: The table ID to parse.
        :param cols: Additional columns to assign to the resulting DataFrame.
        :return: A transformed DataFrame.
        """
        logger.debug(f"Fetching data from endpoint: {endpoint}")
        raw_data = self.datasource.get_data(endpoint=endpoint, table_id=table_id)
        raw_data = raw_data.assign(**cols) if cols else raw_data
        
        transformer = self.transformer_cls()
        transformed_data = transformer.transform(raw_data)
        logger.info(f"Transformed data with {self.transformer_cls.__name__}")
        return transformed_data
    
    def parse_config(self, dataset_name: str) -> None:
        """
        Parses the configuration for a specific dataset.

        :param dataset_name: The dataset name to configure.
        :raises ValueError: If the dataset name is not in the configuration.
        """
        if dataset_name not in self.config['datasets']:
            raise ValueError(f"Dataset name '{dataset_name}' not found in configuration.")
        
        dataset_config = self.config['datasets'][dataset_name]
        
        self.table_id = dataset_config['table_id']
        self.transformer_cls = self.get_transformer(dataset_config['transformer'])
        self.positions = dataset_config.get('positions')
        self.endpoint_template = dataset_config['endpoint_template']
        logger.info(f"Parsed configuration for dataset: {dataset_name}")
    
def main(dataset_name: str, week: int = None):
    connector = SeleniumConnector(BASE_URL, driver_path=DRIVER_PATH)
    parser = HTMLParser()

    with connector:
        datasource = FantasyProsDatasource(connector, parser=parser)
        controller = FantasyProsStrategy(datasource)
        df = controller.run(dataset_name, week)
        df.to_csv(f"{dataset_name}_controller.csv", index=False)

    
if __name__ == "__main__":
    valid_keys = list(FANTASY_PROS_CONFIG.keys())

    user_input = input(f"Enter one of the following keys: {', '.join(valid_keys)}: ")

    while user_input not in valid_keys:
        logger.error("Invalid key entered. Please choose a valid option.")
        user_input = input(f"Enter one of the following keys: {', '.join(valid_keys)}: ")

    main(user_input)

