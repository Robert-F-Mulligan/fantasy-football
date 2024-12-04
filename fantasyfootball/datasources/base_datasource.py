from abc import ABC, abstractmethod
import pandas as pd
from fantasyfootball.connectors.base_connector import BaseConnector
from fantasyfootball.parsers.base_parser import BaseParser


class BaseDataSource(ABC):
    def __init__(self, connector: BaseConnector, parser: BaseParser):
        self.connector = connector
        self.parser = parser

    @abstractmethod
    def get_data(self, url: str) -> pd.DataFrame:
        """Get the final DataFrame from the data source"""
        pass
