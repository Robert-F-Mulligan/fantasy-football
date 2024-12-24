from abc import ABC, abstractmethod
import logging
import pandas as pd
import fantasyfootball.connectors  # Register connectors
from fantasyfootball.factories.connector_factory import ConnectorFactory
import fantasyfootball.datasources  # Register datasources
from fantasyfootball.factories.datasource_factory import DatasourceFactory
import fantasyfootball.transformers  # Register transformers
from fantasyfootball.factories.transformer_factory import TransformerFactory
import fantasyfootball.parsers  # Register parsers
from fantasyfootball.factories.parser_factory import ParserFactory

logger = logging.getLogger(__name__)

class BaseStrategy(ABC):
    factory_mapping = {
        'base_url': lambda cfg: cfg.get('base_url'),
        'connector': lambda cfg: (
            ConnectorFactory.create(cfg['connector'], base_url=cfg.get('base_url'))
            if 'connector' in cfg else None
        ),
        'parser': lambda cfg: (
            ParserFactory.create(cfg['parser'])
            if 'parser' in cfg else None
        ),
        'datasource': lambda cfg: (
            DatasourceFactory.create(cfg['datasource'])
            if 'datasource' in cfg else None
        ),
        'transformer': lambda cfg: (
            TransformerFactory.create(cfg['transformer'])
            if 'transformer' in cfg else None
        ),
        'table_id': lambda cfg: cfg.get('table_id'),
        'endpoint_template': lambda cfg: cfg.get('endpoint_template'),
    }

    def __init__(self, combined_config: dict, **kwargs):
        """
        Initialize the strategy with its combined configuration.
        :param combined_config: The combined configuration for the datasource and dataset.
        :param kwargs: Additional parameters for the strategy (optional).
        """
        self.combined_config = {**combined_config, **kwargs}
        self._load_config()

    @abstractmethod
    def run(self, save_to_csv: bool = False) -> pd.DataFrame:
        """Execute the strategy and return the data."""
        pass

    def _load_config(self):
        """
        Dynamically loads configuration using the factory mapping.
        """
        for attr_name, factory_func in self.factory_mapping.items():
            value = factory_func(self.combined_config)
            setattr(self, attr_name, value)

        # Load additional attributes from the combined config
        additional_attrs = {key: value for key, value in self.combined_config.items() if key not in self.factory_mapping}
        for key, value in additional_attrs.items():
            setattr(self, key, value)

    def save_to_csv(self, data: pd.DataFrame, filename: str, append: bool = False):
        """
        Saves a DataFrame to a CSV file.

        :param data: The DataFrame to save.
        :param output_file: Path to the CSV file.
        :param mode: Write mode, 'w' for write (default) or 'a' for append.
        :param include_header: Whether to include the header in the file (default is True).
        """
        if data.empty:
            logger.warning("Attempted to save an empty DataFrame. Skipping write.")
            return
        
        mode = 'a' if append else 'w'
        header = not append

        try:
            logger.info(f"{'Appending' if append else 'Writing'} data to CSV: {filename}")
            data.to_csv(filename, mode=mode, header=header, index=False)

        except Exception as e:
            logger.exception(f"Failed to save data to CSV: {e}")
            raise
        
    def get_filename(self, *args) -> str:
        """
        Generates a filename based on the dataset name and optional positional arguments.

        :param args: Positional arguments to modify the filename.
        :return: The dynamically generated filename.
        """
        filename = f"{self.dataset_name}_strategy"

        if args:
            filename += "_" + "_".join(str(arg) for arg in args)

        filename += ".csv"

        return filename


if __name__ == "__main__":
    from fantasyfootball.utils.logging_config import setup_logging
    setup_logging()

    # Test the BaseStrategy class
    config = {
            "datasource": "profootballreference",
            "table_id": "stats",
            "href_table_id": "fantasy",
            "endpoint_template": "/players/{last_name_letter}/{player_id}/gamelog/{year}/",
            "year_endpoint_template": "years/{year}/fantasy.htm",
            "transformer": "prf_game_by_game",
            "strategy": "game_by_game",
            "max_players_per_year": 5,
            "min_year": 2023,
            "max_year": 2024
        }

    class SampleStrategy(BaseStrategy):
        def run(self):
            return f"Running strategy with config: {self.__dict__}"

    strategy = SampleStrategy(config)
    strategy._load_config()
    print(strategy.base_url)
    print(strategy.connector)
    print(strategy.parser)
    print(strategy.datasource)
    print(strategy.transformer)
    print(strategy.table_id)
    print(strategy.endpoint_template)
    print(strategy.factory_mapping)
    print(strategy.__dict__)