import logging
from typing import Optional
import pandas as pd
from fantasyfootball.strategies.base_strategy import BaseStrategy
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

@StrategyFactory.register("fantasypros")
class FantasyProsStrategy(BaseStrategy):
    def __init__(self, datasource_config, dataset_config):
        super().__init__(datasource_config, dataset_config)
        """
        Initializes the controller with the base URL and endpoints.
        
        :param base_url: Base URL for Pro Football Reference.
        :param endpoints: Dictionary mapping endpoint paths to table IDs.
        """

        self.all_data = []

    def run(self, week: Optional[int] = 1) -> pd.DataFrame:
        """
        Executes the data retrieval and transformation process for a dataset.

        :param dataset_name: The name of the dataset to process.
        :param week: Optional week number for weekly datasets.
        :return: A concatenated DataFrame containing all processed data.
        """
        self.parse_config()

        with self.connector as connector:
            self.datasource = DatasourceFactory.create(self.dataset_config['datasource'],
                                                       connector=connector,
                                                       parser=self.parser)

            if self.positions:
                for pos in self.positions:
                    try:
                        logger.info(f"Processing position: {pos}")
                        endpoint = self.endpoint_template.format(position=pos, week=week)
                        data = self.get_data(connector,
                                             endpoint, 
                                             self.table_id, 
                                             position=pos)
                        if not data.empty:
                            self.all_data.append(data)
                    except Exception as e:
                        logger.error(f"Failed to process position {pos} at endpoint {endpoint}: {e}")
            else:
                endpoint = self.endpoint_template
                data = self.get_data(connector,
                                     endpoint, 
                                     self.table_id)
                logger.info(f'Returned a df with a shape of {data.shape}')
                if not data.empty:
                    self.all_data.append(data)

            if self.all_data:
                concatenated_data = pd.concat(self.all_data, ignore_index=True)
                logger.info(f"Successfully processed dataset")
                return concatenated_data
            else:
                logger.warning(f"No data collected for dataset")
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
        
        transformed_data = self.transformer.transform(raw_data)
        logger.info(f"Transformed data successfully")
        return transformed_data
    
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
        self.positions = self.dataset_config.get('positions')
        logger.info(f"Parsed configuration for dataset")

    
if __name__ == "__main__":
    from fantasyfootball.utils.logging_config import setup_logging

    setup_logging()

    datasource_config = {
            "base_url": "https://www.fantasypros.com",
            "connector": "selenium",
            "parser": "html"
        }
    dataset_config = {
            "datasource": "fantasypros",
            "table_id": "ranking-table",
            "endpoint_template": "nfl/rankings/ppr-cheatsheets.php",
            "transformer": "fantasy_pros_draft",
            "strategy": "fantasypros"
        }
    strat = FantasyProsStrategy(datasource_config=datasource_config,
                                dataset_config=dataset_config)
    
    df = strat.run()
    print(df.head())
#     valid_keys = list(FANTASY_PROS_CONFIG.keys())

#     user_input = input(f"Enter one of the following keys: {', '.join(valid_keys)}: ")

#     while user_input not in valid_keys:
#         logger.error("Invalid key entered. Please choose a valid option.")
#         user_input = input(f"Enter one of the following keys: {', '.join(valid_keys)}: ")

#     main(user_input)

