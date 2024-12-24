import sys
import json
import logging
import argparse
import pandas as pd
from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.factories.strategy_factory import StrategyFactory
from fantasyfootball.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)

setup_logging()

class DataFacade:
    def __init__(self, config: dict):
        self.config = config

    def get_data(self, dataset_name: str, save_to_csv: bool = False, **kwargs) -> pd.DataFrame:
        """
        Retrieves data for a specific dataset by delegating the task to the appropriate strategy.

        It passes the dataset's configuration along with any additional arguments (`kwargs`)
        to the selected strategy for data processing. Optionally, it can save the data to CSV.

        :param dataset_name: The name of the dataset to retrieve (e.g., 'nflfastr').
        :param save_to_csv: A flag to decide whether to save the retrieved data to a CSV file.
        :param kwargs: Additional keyword arguments to be passed to the strategy.
        :return: A pandas DataFrame containing the processed data.
        """
        try:
            dataset_config = self.config['datasets'][dataset_name]
            datasource_name = dataset_config['datasource']
            datasource_config = self._get_datasource_config(datasource_name)

            # Combine configurations and add dataset_name
            combined_config = {**datasource_config, **dataset_config, 'dataset_name': dataset_name}

            strategy_name = combined_config['strategy']
            strategy_instance = self._get_strategy_instance(strategy_name, combined_config, **kwargs)

            return strategy_instance.run(save_to_csv=save_to_csv)
        
        except KeyError as e:
            logger.error(f"Dataset '{dataset_name}' configuration is missing: {e}")
            raise
        except Exception as e:
            logger.error(f"Error while getting data for dataset '{dataset_name}': {e}", exc_info=True)
            raise

    def _get_datasource_config(self, datasource_name: str) -> dict:
        """
        Retrieve the configuration for a specific datasource.
        """
        return self.config['datasources'][datasource_name]

    def _get_strategy_instance(self, strategy_name: str, combined_config: dict, **kwargs) -> BaseStrategy:
        """
        Returns the strategy instance from the StrategyFactory based on the strategy name.
        """
        return StrategyFactory().create(strategy_name, combined_config=combined_config, **kwargs)

    def list_available_datasets(self):
        """
        Prints out all available dataset names to the command line.
        """
        datasets = self.config['datasets']
        print("Available datasets:")
        for dataset in datasets.keys():
            print(f"- {dataset}")
        print("\nPlease pass one of the above dataset names to fetch data.")

def load_config(path=r'config\data_config.json') -> dict:
    """
    Loads the configuration file.
    """
    with open(path, 'r') as f:
        config = json.load(f)
    return config

def parse_args():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Data Facade CLI")
    parser.add_argument('--dataset_name', type=str, help="The name of the dataset to retrieve")
    parser.add_argument('--list', action='store_true', help="List available datasets")
    return parser.parse_args()

def main():
    """
    Main entry point for running the facade from the command line.
    """
    config = load_config()
    facade = DataFacade(config)

    args = parse_args()

    if args.list:
        facade.list_available_datasets()
    else:
        if not args.dataset_name:
            facade.list_available_datasets()

        dataset_name = args.dataset_name
        while not dataset_name:
            print("Error: You must provide a dataset name.")
            dataset_name = input("Please enter a dataset name from the available options: ").strip()
        
        while dataset_name not in facade.config['datasets']:
            print(f"Error: '{dataset_name}' is not a valid dataset.")
            dataset_name = input("Please enter a valid dataset name from the available options: ").strip()

        try:
            data = facade.get_data(dataset_name=dataset_name, save_to_csv=True)
            print(type(data))
            data.to_csv(f"{dataset_name}_data.csv", index=False)
        except KeyError:
            print(f"Error: The dataset '{dataset_name}' is not valid. Please try again.")
        except KeyboardInterrupt:
            print("\nProcess interrupted. Exiting.")
            sys.exit(0)


if __name__ == "__main__":
    # main()
    facade = DataFacade(load_config())
    data_set = 'nflfastr_pbp'
    #data_set = 'year_by_year'
    # df = facade.get_data(data_set,
    #                      min_year=2021,
    #                      max_year=2023)
    # data_set = 'game_by_game'
    df = facade.get_data(data_set, save_to_csv=True)

    # df.to_csv(f'data_facade_{data_set}.csv', index=False)
