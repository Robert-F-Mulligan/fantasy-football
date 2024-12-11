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

    def _drop_columns(self, columns: list = None):
        """Drops columns"""
        logger.debug("Cleaning columns: dropping unwanted columns.")
        if columns:
            self.df = self.df.drop(columns=columns)
        return self

    def _reindex_and_fill(self, column_order: list, fill_value=0, dtype_map: dict = None):
        """Reorders columns, fills missing values, and casts data types."""
        logger.debug("Reindexing columns and filling missing values.")
        self.df = self.df.reindex(columns=column_order, fill_value=fill_value).fillna(fill_value)
        if dtype_map:
            self.df = self.df.astype(dtype_map)
        return self
    
    def _drop_invalid_rows(self, col: str = 'rk', value: str = None, condition_type: str = 'exact'):
        """
        Drops rows based on a condition in the specified column.
        
        :param col: The column to apply the condition on.
        :param value: The value to match or check for in the column.
        :param condition_type: The type of condition ('exact' or 'contains').
        :return: The updated transformer object.
        """
        logger.debug(f"Dropping invalid rows based on column '{col}' with condition '{condition_type}'.")
        
        if col not in self.df.columns:
            logger.warning(f"Column '{col}' not found in DataFrame. No rows were dropped.")
            return self
        
        condition_functions = {
        'exact': lambda col: self.df[col] == value,
        'contains': lambda col: self.df[col].astype(str).str.contains(value, na=False),
        'na': lambda col: self.df[col].isna()
        }

        condition_func = condition_functions.get(condition_type)
        if not condition_func:
            raise ValueError(f"Unsupported condition_type: {condition_type}. Supported types are: {list(condition_functions.keys())}")
        
        condition = condition_func(col)
        self.df = self.df.loc[~condition]
        logger.debug(f"Rows dropped where '{col}' {condition_type} '{value}'. Remaining rows: {len(self.df)}")
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

    DROP_COLS = ['fantasy_fantpt', 'fantasy_ppr', 'fantasy_dkpt', 'fantasy_fdpt', 'fantasy_vbd']

    def __init__(self, dataframe: pd.DataFrame = None):
        """
        Initializes the transformer with optional DataFrame.
        :param dataframe: The DataFrame to transform (optional).
        """
        logger.info("Initializing YearByYearTransformer.")
        self.df = dataframe

    def transform(self, dataframe: pd.DataFrame = None) -> pd.DataFrame:
        """Performs the entire transformation process."""
        if dataframe is not None:
            self.df = dataframe

        if self.df is None:
            raise ValueError("No DataFrame set for transformation.")

        logger.info("Starting year-by-year transformation process.")
        return (
            self._drop_columns(columns=self.DROP_COLS)
                ._rename_columns(self.COLUMN_RENAME_MAP)
                ._standardize_player_names()
                ._reindex_and_fill(self.FINAL_COLUMN_ORDER)
                ._drop_invalid_rows(col='rk', value='Rk', condition_type='exact')
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
        '1': 'home/away',
        'Fumbles_Fmb': 'fumbles',
        'Fumbles_FL': 'fumbles_lost',
        'receiving_ctch%': 'receiving_ctch_pct'
    }

    FINAL_COLUMN_ORDER = [
        'date', 'week', 'player_id', 'player_name', 'pos', 'year', 
        'age', 'tm', 'home/away', 'opp', 'result', 'off. snaps_num',
        'passing_cmp', 'passing_att', 'passing_yds', 'passing_td', 'passing_int',
        'rushing_att', 'rushing_yds', 'rushing_y/a', 'rushing_td',
        'receiving_tgt', 'receiving_rec', 'receiving_yds', 'receiving_y/r', 'receiving_td',  'receiving_ctch_pct', 'receiving_y/tgt',
        'fumbles', 'fumbles_lost'
    ]

    def __init__(self, dataframe: pd.DataFrame = None):
        """
        Initializes the transformer with optional DataFrame.
        :param dataframe: The DataFrame to transform (optional).
        """
        logger.info("Initializing GameByGameTransformer.")
        self.df = dataframe

    def transform(self, dataframe: pd.DataFrame = None) -> pd.DataFrame:
        """
        Performs the entire transformation process.
        player_id, player_name and pos are scraped through HTML and are added at the datasource level
        """
        if dataframe is not None:
            self.df = dataframe

        if self.df is None:
            raise ValueError("No DataFrame set for transformation.")

        logger.info("Starting game-by-game transformation process.")
        return (
            self._rename_columns(self.COLUMN_RENAME_MAP)
                ._handle_home_away()
                ._reindex_and_fill(self.FINAL_COLUMN_ORDER)
                ._drop_invalid_rows(col='date', value='Games', condition_type='contains')
                ._drop_invalid_rows(col='age', condition_type='na')
                ._drop_invalid_rows(col='off. snaps_num', value='Inactive', condition_type='exact')
                ._convert_pct_to_float(cols=['receiving_ctch_pct'])
                .df
        )

    def _handle_home_away(self):
        logger.debug("Handling home/away column.")
        self.df['home/away'] = self.df['home/away'].replace({'@': 'Away'}).fillna('Home')
        return self
    
    def _convert_pct_to_float(self, cols: list[str] | str):
        logger.debug("Converting pct to float.")
        if isinstance(cols, str):
            cols = [cols]
        
        col_map = {
            col: lambda x: x[col].str.rstrip('%').astype(float) 
            for col in cols 
            if col in self.df.columns and self.df[col].dtype == 'object'
        }
        missing_cols = set(cols) - set(col_map.keys())
        if missing_cols:
            logger.warning(f"The following columns were not converted (missing or non-string): {missing_cols}")

        if col_map:
            self.df = self.df.assign(**col_map)
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
        # df = datasource.get_data(endpoint='years/2024/fantasy.htm', table_id='fantasy')
        # transformer = YearByYearTransformer(df)
        # df = transformer.transform(2024)
        # print(df.head())
        df = datasource.get_data(endpoint='players/J/JacoJo01/gamelog/2022/', table_id='stats')
        # transformer = YearByYearTransformer(df)
        # df = transformer.transform(2024)
        print(df.head())
