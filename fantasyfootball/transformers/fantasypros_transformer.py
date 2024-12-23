import pandas as pd
import logging
from fantasyfootball.transformers.base_transformer import BaseTransformer
from fantasyfootball.factories.transformer_factory import TransformerFactory

logger = logging.getLogger(__name__)

@TransformerFactory.register('fantasy_pros_rankings')
class RankingsTransfomer(BaseTransformer):
    """Encapsulates transformation logic for ranking data."""

    COLUMN_RENAME_MAP = {
        'player name': 'player_name',
        'matchup (?)': 'matchup_rating',
        'start/sit': 'start_sit_rating',
        'proj. fpts': 'projected_fantasy_points'
    }

    FINAL_COLUMN_ORDER = ['rk', 'as_of_date', 'player_name', 'pos', 'team', 'opp', 'matchup_rating', 'start_sit_rating', 'projected_fantasy_points']

    DROP_COLS = ['wsis']

    def __init__(self, dataframe: pd.DataFrame = None):
        """
        Initializes the transformer with optional DataFrame.
        :param dataframe: The DataFrame to transform (optional).
        """
        super().__init__(dataframe)

    def transform(self, dataframe: pd.DataFrame = None) -> pd.DataFrame:
        """Performs the entire transformation process."""
        if dataframe is not None:
            self.dataframe = dataframe

        if self.dataframe is None:
            raise ValueError("No DataFrame set for transformation.")

        logger.info("Starting Fantasy Pros rankings transformation process.")
        return (
            self._drop_columns(columns=self.DROP_COLS)
                ._rename_columns(self.COLUMN_RENAME_MAP)
                ._drop_rows(condition = self.dataframe['matchup_rating']=='-')
                ._parse_matchup()
                ._standardize_player_names()
                ._reindex_and_fill(self.FINAL_COLUMN_ORDER)
                .dataframe
        )

    def _standardize_player_names(self):
        logger.debug("Standardizing player names and assigning pos column.")
        col = 'player_name'
        if col not in self.dataframe.columns:
            raise ValueError("Column not found in DF. Make sure rename logic has been applied already.")
        self.dataframe['team'] = (self.dataframe[col]
                          .str.split('(').str[-1]
                          .str.rsplit(')').str[0].str.strip()
        )
        self.dataframe[col] = (self.dataframe[col]
                                  .str.split('(').str[0].str.strip()
        )
        logger.debug("Player names standardized and pos column has been created.")
        return self
    
    def _parse_matchup(self):
        logger.debug("Extracting matchup score.")
        col = 'matchup_rating'
        if col not in self.dataframe.columns:
            raise ValueError("Column not found in DF. Make sure rename logic has been applied already.")
        self.dataframe[col] = (
            self.dataframe[col]
            .str.split(' ').str[0]
            .astype(int)
        )
        return self
    
@TransformerFactory.register('fantasy_pros_projections')
class ProjectionsTransfomer(BaseTransformer):
    """Encapsulates transformation logic for ranking data."""

    COLUMN_RENAME_MAP = {
        'player': 'player_name',
        'misc_fpts': 'projected_fantasy_points',
        'misc_fl': 'fumbles_lost',
    }

    FINAL_COLUMN_ORDER = ['as_of_date', 'player_name', 'pos', 'team', 
                          'receiving_rec', 'receiving_yds', 'receiving_tds',
                          'rushing_att', 'rushing_yds', 'rushing_tds',
                          'passing_att', 'passing_cmp', 'passing_yds', 'passing_tds', 'passing_ints',
                          'fumbles_lost', 'projected_fantasy_points']

    def __init__(self, dataframe: pd.DataFrame = None):
        """
        Initializes the transformer with optional DataFrame.
        :param dataframe: The DataFrame to transform (optional).
        """
        super().__init__(dataframe)

    def transform(self, dataframe: pd.DataFrame = None) -> pd.DataFrame:
        """Performs the entire transformation process."""
        if dataframe is not None:
            self.dataframe = dataframe

        if self.dataframe is None:
            raise ValueError("No DataFrame set for transformation.")

        logger.info("Starting Fantasy Pros projections transformation process.")
        return (
            self._rename_columns(self.COLUMN_RENAME_MAP)
                ._standardize_player_names()
                ._reindex_and_fill(self.FINAL_COLUMN_ORDER)
                .dataframe
        )

    def _standardize_player_names(self):
        logger.debug("Standardizing player names and assigning pos column.")
        col = 'player_name'
        if col not in self.dataframe.columns:
            raise ValueError("Column not found in DF. Make sure rename logic has been applied already.")
        self.dataframe['team'] = (self.dataframe[col]
                          .str.split(' ')
                          .str[-1].str.strip()
        )
        self.dataframe[col] = (self.dataframe[col]
                                  .str.rsplit(' ', n=1).str[0].str.strip()
        )
        logger.debug("Player names standardized and pos column has been created.")
        return self

@TransformerFactory.register('fantasy_pros_draft')
class DraftTransfomer(BaseTransformer):
    """Encapsulates transformation logic for draft rankings data."""

    COLUMN_RENAME_MAP = {
        'player name': 'player_name',
        'sos': 'strength_of_schedule',
        'ecr vs adp': 'ecr_vs_adp',
        'pos': 'pos_rk'
    }

    FINAL_COLUMN_ORDER = ['rk', 'player_name', 'pos', 'pos_rk', 'team', 
                            'bye', 'strength_of_schedule', 'ecr_vs_adp', 'as_of_date']

    def __init__(self, dataframe: pd.DataFrame = None):
        """
        Initializes the transformer with optional DataFrame.
        :param dataframe: The DataFrame to transform (optional).
        """
        super().__init__(dataframe)

    def transform(self, dataframe: pd.DataFrame = None) -> pd.DataFrame:
        """Performs the entire transformation process."""
        if dataframe is not None:
            self.dataframe = dataframe

        if self.dataframe is None:
            raise ValueError("No DataFrame set for transformation.")

        logger.info("Starting Fantasy Pros draft transformation process.")
        return (
            self._rename_columns(self.COLUMN_RENAME_MAP)
                ._drop_rows(condition=self.dataframe['player_name'].isna())
                ._standardize_player_names()
                ._parse_sos()
                ._parse_pos()
                ._reindex_and_fill(self.FINAL_COLUMN_ORDER)
                .dataframe
        )
    
    def _standardize_player_names(self):
        logger.debug("Standardizing player names and assigning pos column.")
        col = 'player_name'
        if col not in self.dataframe.columns:
            raise ValueError("Column not found in DF. Make sure rename logic has been applied already.")
        self.dataframe['team'] = self.dataframe[col].str.extract(r'\((\w+)\)')
        self.dataframe[col] = self.dataframe[col].str.extract(r'^(.*) \(\w+\)')
        logger.debug("Player names standardized and pos column has been created.")
        return self
    
    def _parse_sos(self):
        logger.debug("Extracting SOS score.")
        col = 'strength_of_schedule'
        if col not in self.dataframe.columns:
            raise ValueError("Column not found in DF. Make sure rename logic has been applied already.")
        self.dataframe[col] = (
            self.dataframe[col]
            .str.split(' ').str[0]
            .replace({'-': 0})
            .astype(int)
        )
        return self
    
    def _parse_pos(self):
        logger.debug("Exracting position from position rank.")
        col = 'pos_rk'
        if col not in self.dataframe.columns:
            raise ValueError("Column not found in DF. Make sure rename logic has been applied already.")
        self.dataframe['pos'] = self.dataframe['pos_rk'].str.extract(r'([A-Za-z]+)')
        return self


if __name__ == "__main__":
    from fantasyfootball.connectors.selenium_connector import SeleniumConnector
    from fantasyfootball.parsers.html_parser import HTMLParser
    from fantasyfootball.datasources.fantasypros import FantasyProsDatasource
    from fantasyfootball.utils.logging_config import setup_logging

    setup_logging()
    
    BASE_URL =  'https://www.fantasypros.com'
    connector = SeleniumConnector(BASE_URL)
    parser =  HTMLParser()
    pos = 'qb'

    fp_map =  {
        'projections':
        {'table_id': 'data',
         'endpoint': f'nfl/projections/{pos}.php?week=draft&scoring=PPR&week=12',
         'transformer': ProjectionsTransfomer},
         'weekly_rank':
         {'table_id': 'ranking-table',
         'endpoint': f'nfl/rankings/ppr-{pos}.php',
          'transformer': RankingsTransfomer},
          'draft':
        {'table_id': 'ranking-table',
         'endpoint': f'nfl/rankings/ppr-cheatsheets.php',
         'transformer': DraftTransfomer},
    }
    fp_type = 'draft'
    config = fp_map.get(fp_type)

    with connector:
        data = FantasyProsDatasource(connector, parser=parser)
        href = config.get('endpoint')
        table_id = config.get('table_id')
        #additional_cols = {'pos': pos.upper()}
        additional_cols = {}
        df = (data.get_data(endpoint=href, table_id=table_id)
              .pipe(data.assign_columns, **additional_cols)
        )
        df.to_csv(f'{fp_type}_raw_data.csv', index=False)
        # print(df)
        transfomer = config.get('transformer')()
        trans_df = transfomer.transform(df)     
        trans_df.to_csv('tf_data.csv', index=False)
        # get team by DI or at DS level
