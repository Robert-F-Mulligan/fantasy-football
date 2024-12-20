import json
import pandas as pd
from fantasyfootball.factories.strategy_factory import StrategyFactory

class DataFacade:
    def __init__(self, config: dict):
        self.config = config

    def get_data(self, datasource_name: str, dataset_name: str, **kwargs) -> pd.DataFrame:
        datasource_config = self.config['datasources'][datasource_name]

        strategy_name = datasource_config['datasets'][dataset_name]['strategy']
        strategy_class = StrategyFactory().create(strategy_name, config=self.config, datasource_config=datasource_config)
        
        return strategy_class.run(dataset_name, **kwargs)
    
def load_config(path=r'config\data_config.json') -> dict:
    with open(path, 'r') as f:
        config = json.load(f)
    return config

if __name__ == "__main__":
    config = load_config()
    facade = DataFacade(config)
    datasource_name = 'fantasypros'
    data = facade.get_data(datasource_name='fantasypros', dataset_name='projections', week=1)
    print(data)