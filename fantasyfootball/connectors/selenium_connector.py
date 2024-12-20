import logging
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fantasyfootball.connectors.base_connector import BaseConnector
from fantasyfootball.utils.retry_decorator import retry_decorator
from fantasyfootball.factories.connector_factory import ConnectorFactory

logger = logging.getLogger(__name__)

@ConnectorFactory.register("selenium")
class SeleniumConnector(BaseConnector):
    def __init__(self, base_url: str, driver_path: str, headless: bool = True):
        super().__init__(base_url)
        self.driver_path = driver_path
        self.headless = headless
        self.driver = None

    def __enter__(self):
        """Set up the Selenium driver."""
        options = Options()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--log-level=3")
        #options.add_argument("--window-size=1920,1200")
        service = Service(self.driver_path)
        self.driver = webdriver.Chrome(service=service, options=options)
        logger.info("Selenium driver initialized.")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Quit the Selenium driver."""
        if self.driver:
            self.driver.quit()
            logger.info("Selenium driver shut down.")

    @retry_decorator(retries=3, delay=2, backoff_factor=2)
    def fetch(self, endpoint: str, table_id: str = None, sleep: int = 5) -> str:
        """Fetch the HTML content of the constructed URL using Selenium."""
        if not self.driver:
            raise RuntimeError("Selenium driver is not initialized. Use the connector in a context manager.")
        
        url = self.construct_url(endpoint)  # Construct the full URL
        try:
            logger.info(f"Fetching URL: {url}")
            self.driver.get(url)
            if table_id:
                WebDriverWait(self.driver, sleep).until(
                    EC.presence_of_element_located((By.ID, table_id))
                )
            else:
                time.sleep(sleep)
            return self.driver.page_source
        except Exception as e:
            logger.error(f"Error fetching the page: {e}")
            raise

    
if __name__ == "__main__":
    from fantasyfootball.utils.logging_config import setup_logging

    setup_logging()

    driver_path = r'C:\Users\rmull\python-projects\fantasy-football\chrome-driver\chromedriver.exe' 
    base_url = 'https://www.fantasypros.com'
    endpoint = 'nfl/projections/qb.php?week=draft&scoring=PPR&week=12'
    
    with SeleniumConnector(base_url=base_url, driver_path=driver_path) as connector:
        try:
            html_content = connector.fetch(endpoint, table_id='data')
            print(type(html_content))
        except Exception as e:
            logger.error(f"Operation failed: {e}")

