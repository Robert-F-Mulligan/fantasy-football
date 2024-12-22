import logging
from datetime import datetime
import pandas as pd
from fantasyfootball.connectors.selenium_connector import SeleniumConnector
from fantasyfootball.parsers.html_parser import HTMLParser
from fantasyfootball.datasources.base_datasource import BaseDataSource
from fantasyfootball.factories.datasource_factory import DatasourceFactory

logger = logging.getLogger(__name__)

@DatasourceFactory.register("fantasypros")
class FantasyProsDatasource(BaseDataSource):
    def __init__(self, connector: SeleniumConnector=None, parser: HTMLParser=None):
        """
        Initializes the datasource with a connector and a parser.
        
        :param connector: An instance of SeleniumConnector to fetch data.
        :param parser: An already instantiated FantasyProsParser for parsing data.
        """
        super().__init__(connector=connector, parser=parser)

    def get_data(self, endpoint: str, table_id: str, **kwargs) -> pd.DataFrame:
        return (
            self._get_data_from_html(endpoint=endpoint,
                                       table_id=table_id,
                                       **kwargs)
                .pipe(self._clean_columns)
                .assign(as_of_date= self._extract_datetime())
        )

    def _extract_datetime(self) -> str:
        """
        Extracts the player's position from the soup object.
        
        :return: Returns a datetime object.
        """
        
        try:
            if not self.parser.soup:
                raise RuntimeError("Parser content must be parsed before extracting datetime.")
        
            time_tags = self.parser.extract("time")

            date_text = next(
            (tag.get_text(strip=True) for tag in time_tags if tag.has_attr("datetime")),
            None
            )
            if date_text:
                date_object = datetime.strptime(date_text, '%b %d, %Y')
                return date_object.isoformat()
            else:
                logger.warning("No valid datetime text found in <time> tags.")
                return None
        except ValueError as ve:
            logger.error(f"Invalid date format for datetime extraction: {ve}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during datetime extraction: {e}")
            return None

if __name__ == "__main__":
    from fantasyfootball.utils.logging_config import setup_logging
    setup_logging()

    pos = 'te'

    fp_map =  {
        'projections':
        {'table_id': 'data',
         'endpoint': f'nfl/projections/{pos}.php?week=draft&scoring=PPR&week=12',
        },
         'weekly_rank':
         {'table_id': 'ranking-table',
         'endpoint': f'nfl/rankings/ppr-{pos}.php',
        },
        'draft':
        {'table_id': 'ranking-table',
         'endpoint': f'nfl/rankings/ppr-cheatsheets.php'},
    }
    key = 'draft'
    config = fp_map.get(key)
   
    BASE_URL =  'https://www.fantasypros.com'
    connector = SeleniumConnector(BASE_URL)
    parser = HTMLParser()
    #'table', id='data'
    with connector:
        data = FantasyProsDatasource()
        href = config.get('endpoint')
        table_id = config.get('table_id')
        df = data.get_data(endpoint=href, 
                           table_id=table_id,
                           connector=connector, 
                           parser=parser)
        df.to_csv(f'{key}_datasource.csv', index=False)
        print(df.head())