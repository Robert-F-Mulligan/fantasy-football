import logging
from fantasyfootball.parsers.base_parser import BaseParser
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class HTMLParser(BaseParser):
    def __init__(self, parser_type: str = "html.parser"):
        super().__init__()
        self.parser_type = parser_type

    def parse(self):
        """Parse HTML content into a BeautifulSoup object."""
        if not self.content:
            raise RuntimeError("Content must be set before parsing.")
        
        try:
            self.soup = BeautifulSoup(self.content, self.parser_type)
            logger.info("HTML parsed successfully.")
            return self.soup
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            raise

    def extract(self, element: str, **kwargs):
        """Extract elements from the parsed content."""
        if not self.soup:
            raise RuntimeError("Content must be parsed before extracting data.")
        
        try:
            print(element)
            print(dict(**kwargs))
            extracted = self.soup.find_all(element, **kwargs)
            logger.info(f"Extracted {len(extracted)} elements of type '{element}'.")
            return extracted
        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            raise


if __name__ == "__main__":
    from fantasyfootball.utils.logging_config import setup_logging
    from fantasyfootball.connectors.selenium_connector import SeleniumConnector

    setup_logging()

    driver_path = r'C:\Users\rmull\python-projects\fantasy-football\chrome-driver\chromedriver.exe' 
    base_url = 'https://www.fantasypros.com'
    
    with SeleniumConnector(base_url=base_url, driver_path=driver_path) as connector:
        try:
            endpoint = 'nfl/projections/qb.php?week=draft&scoring=PPR&week=12'
            raw_html = connector.fetch(endpoint)
            parser = HTMLParser(raw_html)
            soup = parser.parse()
            tables = parser.extract("table", id="data")
            print(tables)

        except Exception as e:
            logger.error(f"Operation failed: {e}") 
