import pandas as pd
import logging

logger = logging.getLogger(__name__)

class DataFrameTransformMixin:
    """Mixin for shared DataFrame transformation logic."""

    def _rename_columns(self, rename_map: dict):
        """Renames columns based on a provided mapping."""
        logger.debug("Renaming columns using provided map.")
        self.df = self.df.rename(columns=rename_map)
        return self

    def _clean_columns(self, drop_columns: list = None, flatten_headers: bool = True):
        """Cleans DataFrame columns."""
        logger.debug("Cleaning columns: dropping unwanted columns and flattening headers if needed.")
        if flatten_headers and hasattr(self.df.columns, 'levels'):  # Check for multi-level columns
            if drop_columns:
                self.df = self.df.drop(columns=drop_columns, level=1)
            self.df.columns = ['_'.join(col) for col in self.df.columns]

        self.df.columns = [col.lower() for col in self.df.columns]
        self.df.columns = [col.split('_')[-1] if 'level' in col else col for col in self.df.columns]
        return self

    def _reindex_and_fill(self, column_order: list, fill_value=0, dtype_map: dict = None):
        """Reorders columns, fills missing values, and casts data types."""
        logger.debug("Reindexing columns and filling missing values.")
        self.df = self.df.reindex(columns=column_order, fill_value=fill_value).fillna(fill_value)
        if dtype_map:
            self.df = self.df.astype(dtype_map)
        return self
    
    def _drop_invalid_rows(self, col: str = 'rk', value: str = 'Rk'):
        logger.debug("Droping invalid rows.")
        condition = self.df[col]==value
        self.df = self.df.loc[~condition]
        return self

class YearByYearTransformer(DataFrameTransformMixin):
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

    def __init__(self, dataframe: pd.DataFrame = None):
        """
        Initializes the transformer with optional DataFrame.
        :param dataframe: The DataFrame to transform (optional).
        """
        logger.info("Initializing YearByYearTransformer.")
        self.df = dataframe

    def transform(self, year: int, dataframe: pd.DataFrame = None) -> pd.DataFrame:
        """Performs the entire transformation process."""
        if dataframe is not None:
            self.df = dataframe

        if self.df is None:
            raise ValueError("No DataFrame set for transformation.")

        logger.info("Starting year-by-year transformation process.")
        self.df['year'] = year
        return (
            self._clean_columns(drop_columns=['FantPt', 'PPR', 'DKPt', 'FDPt', 'VBD'])
                ._rename_columns(self.COLUMN_RENAME_MAP)
                ._standardize_player_names()
                ._reindex_and_fill(self.FINAL_COLUMN_ORDER)
                ._drop_invalid_rows()
                .df
        )

    def _standardize_player_names(self):
        logger.debug("Standardizing player names.")
        self.df['player_name'] = (
            self.df['player_name']
            .str.split('*').str[0]
            .str.split('+').str[0]
        )
        logger.debug("Player names standardized.")
        return self
    
    
class GameByGameTransformer(DataFrameTransformMixin):
    """Encapsulates transformation logic for game-by-game player data."""

    COLUMN_RENAME_MAP = {
        'Unnamed: 6_level_0_Unnamed: 6_level_1': 'home/away',
        'Fumbles_Fmb': 'fumbles',
        'Fumbles_FL': 'fumbles_lost'
    }

    FINAL_COLUMN_ORDER = [
        'date', 'week', 'player_id', 'player_name', 'pos', 'year', 
        'age', 'tm', 'home/away', 'opp', 'result',
        'passing_cmp', 'passing_att', 'passing_yds', 'passing_td', 'passing_int',
        'rushing_att', 'rushing_yds', 'rushing_y/a', 'rushing_td',
        'receiving_tgt', 'receiving_rec', 'receiving_yds', 'receiving_y/r', 'receiving_td',
        'fumbles', 'fumbles_lost'
    ]

    def __init__(self, dataframe: pd.DataFrame = None):
        """
        Initializes the transformer with optional DataFrame.
        :param dataframe: The DataFrame to transform (optional).
        """
        logger.info("Initializing GameByGameTransformer.")
        self.df = dataframe

    def transform(self, player_id: int, year: int, player_name: str, pos: str, dataframe: pd.DataFrame = None) -> pd.DataFrame:
        """Performs the entire transformation process."""
        if dataframe is not None:
            self.df = dataframe

        if self.df is None:
            raise ValueError("No DataFrame set for transformation.")

        logger.info("Starting game-by-game transformation process.")
        self.df['player_id'] = player_id
        self.df['year'] = year
        self.df['player_name'] = player_name
        self.df['pos'] = pos
        return (
            self._clean_columns()
                ._rename_columns(self.COLUMN_RENAME_MAP)
                ._handle_home_away()
                ._reindex_and_fill(self.FINAL_COLUMN_ORDER)
                .df
        )

    def _handle_home_away(self):
        logger.debug("Handling home/away column.")
        self.df['home/away'] = self.df['home/away'].replace({'@': 'Away'}).fillna('Home')
        return self


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
        df = transformer.transform(2024)
        print(df.head())
        df = datasource.get_data(endpoint='years/2023/fantasy.htm', table_id='fantasy')
        transformer = YearByYearTransformer(df)
        df = transformer.transform(2024)
        print(df.head())
