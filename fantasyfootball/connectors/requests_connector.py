import logging
import requests
from fantasyfootball.connectors.base_connector import BaseConnector
from fantasyfootball.utils.retry_decorator import retry_decorator

logger = logging.getLogger(__name__)

class RequestsConnector(BaseConnector):
    def __init__(self, base_url: str = None, headers: dict = None, timeout: int = 10):
        """
        Initialize the connector with base URL, headers, and timeout settings.
        
        :param base_url: The base URL for the API or website.
        :param headers: Headers for the HTTP request (default is a basic User-Agent).
        :param timeout: Timeout for the requests in seconds (default 10).
        """
        self.base_url = base_url
        self.headers = headers or {"User-Agent": "Mozilla/5.0"}
        self.timeout = timeout
        self.session = None

    def __enter__(self):
        """Initialize the session."""
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Clean up the session."""
        if self.session:
            self.session.close()
        if exc_type:
            logger.error(f"Error during connection: {exc_value}")
        return False  # Propagate exceptions

    @retry_decorator(retries=3, delay=2, backoff_factor=2)
    def fetch(self, endpoint: str, params: dict = None) -> str:
        """Fetch raw HTML from the endpoint."""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            logger.info(f"Fetching URL: {url}")
            response = self.session.get(url, params=params, timeout=self.timeout) if self.session else requests.get(
                url, params=params, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()  # Raise an exception for bad responses
            logger.info(f"Request to {url} succeeded with status code {response.status_code}")
            return response.text
        except requests.exceptions.RequestException as e:
            logger.exception(f"HTTP Request failed: {e}")
            raise