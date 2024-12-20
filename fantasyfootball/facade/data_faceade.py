import json
import pandas as pd
import argparse
from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.factories.strategy_factory import StrategyFactory

class DataFacade:
    def __init__(self, config: dict):
        self.config = config

    def get_data(self, dataset_name: str, **kwargs) -> pd.DataFrame:
        """
        Retrieves data based on the dataset_name.
        """
        dataset_config = self.config['datasources']['datasets'][dataset_name]
        datasource_name = dataset_config['datasource']
        
        datasource_config = self._get_datasource_config(datasource_name)

        strategy_name = dataset_config['strategy']
        strategy_class = self._get_strategy_class(strategy_name)

        strategy = strategy_class(datasource_config, dataset_config)
        return strategy.run(**kwargs)
    
    def _get_datasource_config(self, datasource_name: str) -> dict:
        """
        Retrieve the configuration for a specific datasource.
        """
        return self.config['datasources'][datasource_name]

    def _get_strategy_class(self, strategy_name: str) -> BaseStrategy:
        """
        Returns the strategy class from the StrategyFactory based on the strategy name.
        """
        return StrategyFactory().create(strategy_name)
    
    def list_available_datasets(self):
        """
        Prints out all available dataset names to the command line.
        """
        datasets = self.config['datasources']['datasets']
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
    return parser.parse_args()

def main():
    """
    Main entry point for running the facade from the command line.
    """
    config = load_config()
    facade = DataFacade(config)

    args = parse_args()

    if not args.dataset_name:
        facade.list_available_datasets()
    else:
        data = facade.get_data(dataset_name=args.dataset_name)
        print(data)

if __name__ == "__main__":
    main()
