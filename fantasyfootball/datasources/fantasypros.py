import logging
import pandas as pd
from fantasyfootball.connectors.selenium_connector import SeleniumConnector
from fantasyfootball.parsers.html_parser import HTMLParser
from fantasyfootball.datasources.base_datasource import BaseDataSource

logger = logging.getLogger(__name__)

class FantasyProsDatasource(BaseDataSource):
    def __init__(self, connector: SeleniumConnector, parser: HTMLParser):
        """
        Initializes the datasource with a connector and a parser.
        
        :param connector: An instance of SeleniumConnector to fetch data.
        :param parser: An already instantiated FantasyProsParser for parsing data.
        """
        super().__init__(connector, parser)

    def get_data(self, endpoint: str, table_id: str) -> pd.DataFrame:
        return (
            self._get_data_from_html(endpoint=endpoint,
                                       table_id=table_id)
                .pipe(self._clean_columns)
        ) 

if __name__ == "__main__":
    from fantasyfootball.utils.logging_config import setup_logging
    setup_logging()
   
    BASE_URL =  'https://www.fantasypros.com'
    DRIVER_PATH = r'C:\Users\rmull\python-projects\fantasy-football\chrome-driver\chromedriver.exe'
    connector = SeleniumConnector(BASE_URL, driver_path=DRIVER_PATH)
    parser = HTMLParser()
    #'table', id='data'
    with connector:
        data = FantasyProsDatasource(connector, parser=parser)
        href = 'nfl/projections/qb.php?week=draft&scoring=PPR&week=12'
        df = data.get_data(endpoint=href, table_id='data')
        print(df.head())