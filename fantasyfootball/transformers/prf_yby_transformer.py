import pandas as pd
import logging

logger = logging.getLogger(__name__)

class YearByYearTransformer:
    """Encapsulates transformation logic for year-by-year player data."""

    COLUMN_RENAME_MAP = {
        'player': 'player_name',
        'fumbles_fmb': 'fumbles',
        'fumbles_fl': 'fumbles_lost',
        'games_g': 'games',
        'games_gs': 'games_started',
        'fantpos': 'pos',
        'year_': 'year'
    }

    FINAL_COLUMN_ORDER = [
        'rk', 'player_name', 'pos', 'year', 
        'age', 'tm', 'games', 'games_started',
        'passing_cmp', 'passing_att', 'passing_yds', 'passing_td', 'passing_int',
        'rushing_att', 'rushing_yds', 'rushing_y/a', 'rushing_td',
        'receiving_tgt', 'receiving_rec', 'receiving_yds', 'receiving_y/r', 'receiving_td',
        'scoring_2pm',
        'fumbles', 'fumbles_lost',
        'fantasy_posrank', 'fantasy_ovrank'
    ]

    def __init__(self, dataframe: pd.DataFrame, year: int):
        logger.info("Initializing YearByYearTransformer.")
        self.df = dataframe.copy()
        self.year = year

    def transform(self) -> pd.DataFrame:
        """Performs the entire transformation process."""
        logger.info("Starting transformation process.")
        self.df['year'] = self.year
        return (
            self._clean_columns()
            ._rename_columns()
            ._standardize_player_names()
            ._reindex_and_fill()
            ._finalize()
        )

    def _clean_columns(self):
        logger.debug("Cleaning columns: dropping unwanted columns and flattening multi-level headers.")
        if hasattr(self.df.columns, 'levels'):  # Check for multi-level columns
            self.df.drop(columns=['FantPt', 'PPR', 'DKPt', 'FDPt', 'VBD'], level=1, inplace=True)
            self.df.columns = ['_'.join(col) for col in self.df.columns]
        
        self.df.columns = [col.lower() for col in self.df.columns]
        self.df.columns = [col.split('_')[-1] if 'level' in col else col for col in self.df.columns]
        self.df = self.df.loc[self.df['rk'] != 'Rk']
        logger.debug("Columns cleaned.")
        return self

    def _rename_columns(self):
        logger.debug("Renaming columns using COLUMN_RENAME_MAP.")
        self.df.rename(columns=self.COLUMN_RENAME_MAP, inplace=True)
        logger.debug("Columns renamed.")
        return self

    def _standardize_player_names(self):
        logger.debug("Standardizing player names.")
        self.df['player_name'] = (
            self.df['player_name']
            .str.split('*').str[0]
            .str.split('+').str[0]
        )
        logger.debug("Player names standardized.")
        return self

    def _reindex_and_fill(self):
        logger.debug("Reindexing columns and filling missing values.")
        self.df = self.df.reindex(columns=self.FINAL_COLUMN_ORDER, fill_value=0)
        self.df.fillna(0, inplace=True)
        logger.debug("Reindexing and filling completed.")
        return self

    def _finalize(self):
        logger.debug("Finalizing DataFrame transformation.")
        return self.df

if __name__ == "__main__":
    from fantasyfootball.connectors.requests_connector import RequestsConnector
    from fantasyfootball.parsers.html_parser import HTMLParser
    from fantasyfootball.datasources.profootballreference import ProFootballReferenceDataSource
    from fantasyfootball.utils.logging_config import setup_logging

    setup_logging()
    
    connector = RequestsConnector(base_url="https://www.pro-football-reference.com")
    parser =  HTMLParser()
    datasource = ProFootballReferenceDataSource(connector, parser)

    with connector:
        df = datasource.get_data(endpoint='years/2024/fantasy.htm', table_id='fantasy')
        transformer = YearByYearTransformer(df)
        df = transformer.transform()
        print(df.head())

