import logging
import requests
import pandas as pd
from fantasyfootball.connectors.base_connector import BaseConnector
from fantasyfootball.utils.retry_decorator import retry_decorator
from fantasyfootball.factories.connector_factory import ConnectorFactory

logger = logging.getLogger(__name__)

@ConnectorFactory.register("github")
class GitHubConnector(BaseConnector):
    def __init__(self, base_url: str = None):
        """
        Initialize the connector with base URL and timeout settings.

        :param base_url: The base URL for the GitHub repository.
        :param timeout: Timeout for the request (default 10 seconds).
        """
        self.base_url = base_url

    @retry_decorator(retries=3, delay=2, backoff_factor=2)
    def fetch(self, endpoint: str, chunksize: int = None) -> pd.DataFrame:
        """
        Fetch CSV data from the specified GitHub URL endpoint.

        :param endpoint: The GitHub repository path to the CSV file.
        :param chunksize: Number of rows to read per chunk. If None, reads the entire file.
        :return: A pandas DataFrame containing the CSV data.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            logger.info(f"Fetching CSV data from URL: {url}")
            data = pd.read_csv(
                url,
                compression='gzip',
                low_memory=False,
                chunksize=chunksize
            )
            return data
        except Exception as e:
            logger.exception(f"Failed to fetch CSV data from {url}: {e}")
            raise