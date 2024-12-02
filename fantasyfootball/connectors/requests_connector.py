import logging
import requests
from bs4 import BeautifulSoup
from base_connector import BaseConnector
from fantasyfootball.utils.retry_decorator import retry_decorator

logger = logging.getLogger(__name__)

class RequestsConnector(BaseConnector):
    def __init__(self, base_url=None, headers=None, timeout=10):
        self.base_url = base_url
        self.headers = headers or {"User-Agent": "Mozilla/5.0"}
        self.timeout = timeout
        self.session = None

    def __enter__(self):
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.session:
            self.session.close()
        if exc_type:
            logger.error(f"Error during connection: {exc_value}")
        return False  # Propagate exceptions

    @retry_decorator(retries=3, delay=2, backoff_factor=2)
    def fetch(self, endpoint, params=None):
        """Fetch data from the endpoint."""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            logger.info(f"Fetching URL: {url}")
            response = self.session.get(url, params=params, timeout=self.timeout) if self.session else requests.get(
                url, params=params, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            logger.info(f"Request to {url} succeeded with status code {response.status_code}")
            return response.text
        except requests.exceptions.RequestException as e:
            logger.exception(f"HTTP Request failed: {e}")
            raise

    def parse_html(self, html, parser="html.parser") -> BeautifulSoup:
        """Parses HTML."""
        try:
            soup = BeautifulSoup(html, parser)
            logger.info("HTML parsing completed successfully.")
            return soup
        except Exception as e:
            logger.exception(f"Error during HTML parsing: {e}")
            raise

    def get_data(self, endpoint, params=None, parser="html.parser") -> BeautifulSoup:
        """Fetches and parses the data from the endpoint."""
        html = self.fetch(endpoint, params=params)
        return self.parse_html(html, parser)
    
if __name__ == '__main__':
    base_url = 'https://www.pro-football-reference.com'
    resource_link = '/players/H/HallBr03/gamelog/2023/advanced/'
    with RequestsConnector(base_url=base_url) as connector:
        try:
            soup = connector.get_data(resource_link, params={"key": "value"})
            print(soup.prettify())
        except Exception as e:
            logger.error(f"Operation failed: {e}")

# to do - resolve import issue
# default logging
# json config