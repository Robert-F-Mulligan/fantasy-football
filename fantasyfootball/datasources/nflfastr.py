import logging
from datetime import datetime
import pandas as pd
from fantasyfootball.connectors.github_connector import GitHubConnector
from fantasyfootball.parsers.html_parser import HTMLParser
from fantasyfootball.datasources.base_datasource import BaseDataSource
from fantasyfootball.factories.datasource_factory import DatasourceFactory

logger = logging.getLogger(__name__)

@DatasourceFactory.register("nflfastr")
class NflfastrDatasource(BaseDataSource):
    def __init__(self, connector: GitHubConnector= None, parser= None):
        """
        Initializes the datasource with a connector and a parser.
        
        :param connector: An instance of SeleniumConnector to fetch data.
        :param parser: An already instantiated FantasyProsParser for parsing data.
        """
        super().__init__(connector=connector, parser=parser)

    def get_data(self, endpoint: str, connector=None, **kwargs) -> pd.DataFrame:
        self.connector = connector or self.connector

        if not self.connector:
            raise ValueError("Connector must be provided either at init or in get_data.")
        return self.connector.fetch(endpoint=endpoint, **kwargs)


if __name__ == "__main__":
    from fantasyfootball.utils.logging_config import setup_logging
    setup_logging()

    
   
    # BASE_URL =  'https://www.fantasypros.com'
    # connector = SeleniumConnector(BASE_URL)
    # parser = HTMLParser()
    # #'table', id='data'
    # with connector:
    #     data = FantasyProsDatasource()
    #     href = config.get('endpoint')
    #     table_id = config.get('table_id')
    #     df = data.get_data(endpoint=href, 
    #                        table_id=table_id,
    #                        connector=connector, 
    #                        parser=parser)
    #     df.to_csv(f'{key}_datasource.csv', index=False)
    #     print(df.head())