from abc import ABC, abstractmethod
import logging
from bs4 import BeautifulSoup
import requests
import pandas as pd

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    def __init__(self, url: str):
        self.url = url

    @abstractmethod
    def fetch(self, url: str) -> str:
        """Fetch the HTML content of a page."""
        pass

    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML into a BeautifulSoup object."""
        pass

    # @abstractmethod
    # def to_dataframe(self, raw_data: str) -> pd.DataFrame:
    #     """Convert raw data into a DataFrame."""
    #     pass
