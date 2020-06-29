import unittest
from bs4 import BeautifulSoup
import requests
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal
import sys
sys.path.append('..')
from FantasyPros import fantasy_pros_column_clean, fantasy_pros_column_reindex, fantasy_pros_scrape
import config

class TestProcessing(unittest.TestCase):
    def test_fantasy_pros_scrape_rb(self):
        rb_url = f'https://www.fantasypros.com/nfl/projections/rb.php?week=draft&scoring=PPR&week=draft' 
        
        expected = [('Unnamed: 0_level_0', 'Player'),
            (           'RUSHING',    'ATT'),
            (           'RUSHING',    'YDS'),
            (           'RUSHING',    'TDS'),
            (         'RECEIVING',    'REC'),
            (         'RECEIVING',    'YDS'),
            (         'RECEIVING',    'TDS'),
            (              'MISC',     'FL'),
            (              'MISC',   'FPTS')]

        self.assertListEqual(expected, list(fantasy_pros_scrape(rb_url).columns))

    def test_fantasy_pros_scrape_wr(self):
        wr_url = f'https://www.fantasypros.com/nfl/projections/wr.php?week=draft&scoring=PPR&week=draft'

        expected = [('Unnamed: 0_level_0', 'Player'),
            (         'RECEIVING',    'REC'),
            (         'RECEIVING',    'YDS'),
            (         'RECEIVING',    'TDS'),
            (           'RUSHING',    'ATT'),
            (           'RUSHING',    'YDS'),
            (           'RUSHING',    'TDS'),
            (              'MISC',     'FL'),
            (              'MISC',   'FPTS')]

        self.assertListEqual(expected, list(fantasy_pros_scrape(wr_url).columns))

    def test_fantasy_pros_scrape_te(self):
        te_url = f'https://www.fantasypros.com/nfl/projections/te.php?week=draft&scoring=PPR&week=draft'

        expected = [('Unnamed: 0_level_0', 'Player'),
            (         'RECEIVING',    'REC'),
            (         'RECEIVING',    'YDS'),
            (         'RECEIVING',    'TDS'),
            (              'MISC',     'FL'),
            (              'MISC',   'FPTS')]

        self.assertListEqual(expected, list(fantasy_pros_scrape(te_url).columns))

    def test_fantasy_pros_scrape_qb(self):
        qb_url = f'https://www.fantasypros.com/nfl/projections/qb.php?week=draft&scoring=PPR&week=draft'

        expected = [('Unnamed: 0_level_0', 'Player'),
            (           'PASSING',    'ATT'),
            (           'PASSING',    'CMP'),
            (           'PASSING',    'YDS'),
            (           'PASSING',    'TDS'),
            (           'PASSING',   'INTS'),
            (           'RUSHING',    'ATT'),
            (           'RUSHING',    'YDS'),
            (           'RUSHING',    'TDS'),
            (              'MISC',     'FL'),
            (              'MISC',   'FPTS')]

        self.assertListEqual(expected, list(fantasy_pros_scrape(qb_url).columns))

    def test_fantasy_pros_column_clean(self):
        df = pd.DataFrame({
        ('Unnamed: 0_level_0', 'Player'): {0: 'Christian McCaffrey CAR',
        1: 'Saquon Barkley NYG',
        2: 'Ezekiel Elliott JAC',
        3: 'Dalvin Cook MIN',
        4: 'Alvin Kamara NO'},
        ('RUSHING', 'ATT'): {0: 248.3, 1: 267.4, 2: 286.4, 3: 256.3, 4: 193.9},
        ('RUSHING', 'YDS'): {0: 1144.1, 1: 1230.2, 2: 1286.9, 3: 1150.5, 4: 902.5},
        ('RUSHING', 'TDS'): {0: 8.8, 1: 9.6, 2: 10.0, 3: 10.4, 4: 8.4},
        ('RECEIVING', 'REC'): {0: 101.9, 1: 68.6, 2: 61.1, 3: 61.3, 4: 79.6},
        ('RECEIVING', 'YDS'): {0: 841.2, 1: 545.0, 2: 482.1, 3: 534.5, 4: 587.9},
        ('RECEIVING', 'TDS'): {0: 4.0, 1: 2.8, 2: 2.6, 3: 1.8, 4: 3.1},
        ('MISC', 'FL'): {0: 2.5, 1: 1.9, 2: 2.7, 3: 2.3, 4: 2.1},
        ('MISC', 'FPTS'): {0: 372.2, 1: 316.4, 2: 307.6, 3: 298.7, 4: 293.6}
    })

        expected = pd.DataFrame({
        'player_name': {0: 'Christian McCaffrey',
        1: 'Saquon Barkley',
        2: 'Ezekiel Elliott',
        3: 'Dalvin Cook',
        4: 'Alvin Kamara'},
        'rushing_att': {0: 248.3, 1: 267.4, 2: 286.4, 3: 256.3, 4: 193.9},
        'rushing_yds': {0: 1144.1, 1: 1230.2, 2: 1286.9, 3: 1150.5, 4: 902.5},
        'rushing_td': {0: 8.8, 1: 9.6, 2: 10.0, 3: 10.4, 4: 8.4},
        'receiving_rec': {0: 101.9, 1: 68.6, 2: 61.1, 3: 61.3, 4: 79.6},
        'receiving_yds': {0: 841.2, 1: 545.0, 2: 482.1, 3: 534.5, 4: 587.9},
        'receiving_td': {0: 4.0, 1: 2.8, 2: 2.6, 3: 1.8, 4: 3.1},
        'fumbles': {0: 2.5, 1: 1.9, 2: 2.7, 3: 2.3, 4: 2.1},
        'ppr_scoring': {0: 372.2, 1: 316.4, 2: 307.6, 3: 298.7, 4: 293.6},
        'tm': {0: 'CAR', 1: 'NYG', 2: 'JAX', 3: 'MIN', 4: 'NO'}
    })

        assert_frame_equal(expected, fantasy_pros_column_clean(df))

    def test_fantasy_pros_reindex(self):
        df = pd.DataFrame({
        'player_name': {0: 'Christian McCaffrey',
        1: 'Saquon Barkley',
        2: 'Ezekiel Elliott',
        3: 'Dalvin Cook',
        4: 'Alvin Kamara'},
        'rushing_att': {0: 248.3, 1: 267.4, 2: 286.4, 3: 256.3, 4: 193.9},
        'rushing_yds': {0: 1144.1, 1: 1230.2, 2: 1286.9, 3: 1150.5, 4: 902.5},
        'rushing_td': {0: 8.8, 1: 9.6, 2: 10.0, 3: 10.4, 4: 8.4},
        'receiving_rec': {0: 101.9, 1: 68.6, 2: 61.1, 3: 61.3, 4: 79.6},
        'receiving_yds': {0: 841.2, 1: 545.0, 2: 482.1, 3: 534.5, 4: 587.9},
        'receiving_td': {0: 4.0, 1: 2.8, 2: 2.6, 3: 1.8, 4: 3.1},
        'fumbles': {0: 2.5, 1: 1.9, 2: 2.7, 3: 2.3, 4: 2.1},
        'ppr_scoring': {0: 372.2, 1: 316.4, 2: 307.6, 3: 298.7, 4: 293.6},
        'tm': {0: 'CAR', 1: 'NYG', 2: 'DAL', 3: 'MIN', 4: 'NO'}
    })

        expected = pd.DataFrame({
        'id': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
        'player_name': {0: 'Christian McCaffrey',
        1: 'Saquon Barkley',
        2: 'Ezekiel Elliott',
        3: 'Dalvin Cook',
        4: 'Alvin Kamara'},
        'tm': {0: 'CAR', 1: 'NYG', 2: 'DAL', 3: 'MIN', 4: 'NO'},
        'pos': {0: '-', 1: '-', 2: '-', 3: '-', 4: '-'},
        'receiving_rec': {0: 101.9, 1: 68.6, 2: 61.1, 3: 61.3, 4: 79.6},
        'receiving_yds': {0: 841.2, 1: 545.0, 2: 482.1, 3: 534.5, 4: 587.9},
        'receiving_td': {0: 4.0, 1: 2.8, 2: 2.6, 3: 1.8, 4: 3.1},
        'rushing_att': {0: 248.3, 1: 267.4, 2: 286.4, 3: 256.3, 4: 193.9},
        'rushing_yds': {0: 1144.1, 1: 1230.2, 2: 1286.9, 3: 1150.5, 4: 902.5},
        'rushing_td': {0: 8.8, 1: 9.6, 2: 10.0, 3: 10.4, 4: 8.4},
        'passing_att': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
        'passing_cmp': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
        'passing_yds': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
        'passing_td': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
        'passing_int': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0},
        'fumbles': {0: 2.5, 1: 1.9, 2: 2.7, 3: 2.3, 4: 2.1},
        'ppr_scoring': {0: 372.2, 1: 316.4, 2: 307.6, 3: 298.7, 4: 293.6}
    })

        assert_frame_equal(expected, fantasy_pros_column_reindex(df))

if __name__ == "__main__":
    unittest.main()
