import json
import pandas as pd
import argparse
import fantasyfootball.strategies # register strategies
from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.factories.strategy_factory import StrategyFactory
from fantasyfootball.utils.logging_config import setup_logging

setup_logging()

class DataFacade:
    def __init__(self, config: dict):
        self.config = config

    def get_data(self, dataset_name: str, **kwargs) -> pd.DataFrame:
            """
            Retrieves data based on the dataset_name.
            """
            dataset_config = self.config['datasets'][dataset_name]
            datasource_name = dataset_config['datasource']
            datasource_config = self._get_datasource_config(datasource_name)

            # Combine configurations and add dataset_name
            combined_config = {**datasource_config, **dataset_config, 'dataset_name': dataset_name}

            strategy_name = combined_config['strategy']
            strategy_instance = self._get_strategy_instance(strategy_name, combined_config, **kwargs)

            return strategy_instance.run()

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
            data = facade.get_data(dataset_name=dataset_name)
            print(type(data))
            data.to_csv(f"{dataset_name}_data.csv", index=False)
        except KeyError:
            print(f"Error: The dataset '{dataset_name}' is not valid. Please try again.")
        except KeyboardInterrupt:
            print("\nProcess interrupted. Exiting.")
            exit(0)
if __name__ == "__main__":
    # main()
    facade = DataFacade(load_config())
    df = facade.get_data('draft')
    df.to_csv('draft_data_facade.csv', index=False)
