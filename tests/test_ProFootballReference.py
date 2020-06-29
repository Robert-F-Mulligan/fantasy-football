import unittest
from bs4 import BeautifulSoup
import requests
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal
import sys
sys.path.append('..')
from scripts.ProFootballReference import player_href_list_grab , player_id_transform, player_soup_grab, player_name_and_pos_grab, player_table_grab, player_table_transform, player_table_variable_add, player_table_reindex
import scripts.config
import numpy as np

class TestProFootballReference(unittest.TestCase):  
    def test_player_href_list_grab(self):
        year = 2019 
        expected = [
            '/players/M/McCaCh01.htm',
            '/players/J/JackLa00.htm',
            '/players/H/HenrDe00.htm',
            '/players/J/JoneAa00.htm',
            '/players/E/ElliEz00.htm',
            '/players/C/CookDa01.htm'
        ]
        self.assertListEqual(expected, player_href_list_grab(year)[:6])

    def test_player_id_transform(self):
        string = '/players/M/McCaCh01.htm'
        expected = 'M', 'McCaCh01'
        self.assertEqual(expected, player_id_transform(string))

    def test_player_soup_grab(self):
        last_name_letter = 'M'
        player_id = 'McCaCh01'
        year = 2019
        self.assertIsInstance(player_soup_grab(last_name_letter, player_id, year), BeautifulSoup)

    def test_player_table_transform(self):
        df = pd.DataFrame(
            {('Unnamed: 0_level_0', 'Rk'): {0: 1.0, 1: 2.0},
            ('Unnamed: 1_level_0', 'Date'): {0: '2019-09-08', 1: '2019-09-12'},
            ('Unnamed: 2_level_0', 'G#'): {0: 1.0, 1: 2.0},
            ('Unnamed: 3_level_0', 'Week'): {0: 1.0, 1: 2.0},
            ('Unnamed: 4_level_0', 'Age'): {0: 23.093000000000004, 1: 23.096999999999998},
            ('Unnamed: 5_level_0', 'Tm'): {0: 'CAR', 1: 'CAR'},
            ('Unnamed: 6_level_0', 'Unnamed: 6_level_1'): {0: '@', 1: np.nan},
            ('Unnamed: 7_level_0', 'Opp'): {0: 'LAR', 1: 'TAM'},
            ('Unnamed: 8_level_0', 'Result'): {0: 'L 27-30', 1: 'L 14-20'},
            ('Unnamed: 9_level_0', 'GS'): {0: '*', 1: '*'},
            ('Rushing', 'Att'): {0: 19, 1: 16},
            ('Rushing', 'Yds'): {0: 128, 1: 37},
            ('Rushing', 'Y/A'): {0: 6.74, 1: 2.31},
            ('Rushing', 'TD'): {0: 2, 1: 0},
            ('Receiving', 'Tgt'): {0: 11, 1: 6},
            ('Receiving', 'Rec'): {0: 10, 1: 2},
            ('Receiving', 'Yds'): {0: 81, 1: 16},
            ('Receiving', 'Y/R'): {0: 8.1, 1: 8.0},
            ('Receiving', 'TD'): {0: 0, 1: 0},
            ('Receiving', 'Ctch%'): {0: '90.9%', 1: '33.3%'},
            ('Receiving', 'Y/Tgt'): {0: 7.36, 1: 2.67},
            ('Passing', 'Cmp'): {0: 0, 1: 0},
            ('Passing', 'Att'): {0: 0, 1: 0},
            ('Passing', 'Cmp%'): {0: 0, 1: 0},
            ('Passing', 'Yds'): {0: 0, 1: 0},
            ('Passing', 'TD'): {0: 0, 1: 0},
            ('Passing', 'Int'): {0: 0, 1: 0},
            ('Passing', 'Rate'): {0: 0, 1: 0},
            ('Passing', 'Sk'): {0: 0, 1: 0},
            ('Passing', 'Yds.1'): {0: 0, 1: 0},
            ('Passing', 'Y/A'): {0: 0, 1: 0},
            ('Passing', 'AY/A'): {0: 0, 1: 0},
            ('Scoring', '2PM'): {0: 0, 1: 0},
            ('Scoring', 'TD'): {0: 2, 1: 0},
            ('Scoring', 'Pts'): {0: 12, 1: 0},
            ('Fumbles', 'Fmb'): {0: 0, 1: 0},
            ('Fumbles', 'FL'): {0: 0, 1: 0},
            ('Fumbles', 'FF'): {0: 0, 1: 0},
            ('Fumbles', 'FR'): {0: 0, 1: 0},
            ('Fumbles', 'Yds'): {0: 0, 1: 0},
            ('Fumbles', 'TD'): {0: 0, 1: 0},
            ('Off. Snaps', 'Num'): {0: 66.0, 1: 75.0},
            ('Off. Snaps', 'Pct'): {0: '100%', 1: '100%'},
            ('Def. Snaps', 'Num'): {0: 0.0, 1: 0.0},
            ('Def. Snaps', 'Pct'): {0: '0%', 1: '0%'},
            ('ST Snaps', 'Num'): {0: 0.0, 1: 0.0},
            ('ST Snaps', 'Pct'): {0: '0%', 1: '0%'}
        })

        expected = pd.DataFrame(
            {'rk': {0: 1.0, 1: 2.0},
            'date': {0: '2019-09-08', 1: '2019-09-12'},
            'g#': {0: 1.0, 1: 2.0},
            'week': {0: 1.0, 1: 2.0},
            'age': {0: 23.093000000000004, 1: 23.096999999999998},
            'tm': {0: 'CAR', 1: 'CAR'},
            'home/away': {0: 'Away', 1: 'Home'},
            'opp': {0: 'LAR', 1: 'TAM'},
            'result': {0: 'L 27-30', 1: 'L 14-20'},
            'gs': {0: '*', 1: '*'},
            'rushing_att': {0: 19, 1: 16},
            'rushing_yds': {0: 128, 1: 37},
            'rushing_y/a': {0: 6.74, 1: 2.31},
            'rushing_td': {0: 2, 1: 0},
            'receiving_tgt': {0: 11, 1: 6},
            'receiving_rec': {0: 10, 1: 2},
            'receiving_yds': {0: 81, 1: 16},
            'receiving_y/r': {0: 8.1, 1: 8.0},
            'receiving_td': {0: 0, 1: 0},
            'receiving_ctch%': {0: '90.9%', 1: '33.3%'},
            'receiving_y/tgt': {0: 7.36, 1: 2.67},
            'passing_cmp': {0: 0, 1: 0},
            'passing_att': {0: 0, 1: 0},
            'passing_cmp%': {0: 0, 1: 0},
            'passing_yds': {0: 0, 1: 0},
            'passing_td': {0: 0, 1: 0},
            'passing_int': {0: 0, 1: 0},
            'passing_rate': {0: 0, 1: 0},
            'passing_sk': {0: 0, 1: 0},
            'passing_yds.1': {0: 0, 1: 0},
            'passing_y/a': {0: 0, 1: 0},
            'passing_ay/a': {0: 0, 1: 0},
            'scoring_2pm': {0: 0, 1: 0},
            'scoring_td': {0: 2, 1: 0},
            'scoring_pts': {0: 12, 1: 0},
            'fumbles': {0: 0, 1: 0},
            'fumbles_lost': {0: 0, 1: 0},
            'fumbles_ff': {0: 0, 1: 0},
            'fumbles_fr': {0: 0, 1: 0},
            'fumbles_yds': {0: 0, 1: 0},
            'fumbles_td': {0: 0, 1: 0}
        })
        assert_frame_equal(expected, player_table_transform(df))

    def test_player_table_reindex(self):
        df = pd.DataFrame(
            {'rk': {0: 1.0, 1: 2.0},
            'date': {0: '2019-09-08', 1: '2019-09-12'},
            'g#': {0: 1.0, 1: 2.0},
            'week': {0: 1.0, 1: 2.0},
            'age': {0: 23.093000000000004, 1: 23.096999999999998},
            'tm': {0: 'CAR', 1: 'CAR'},
            'home/away': {0: 'Home', 1: 'Home'},
            'opp': {0: 'LAR', 1: 'TAM'},
            'result': {0: 'L 27-30', 1: 'L 14-20'},
            'gs': {0: '*', 1: '*'},
            'rushing_att': {0: 19, 1: 16},
            'rushing_yds': {0: 128, 1: 37},
            'rushing_y/a': {0: 6.74, 1: 2.31},
            'rushing_td': {0: 2, 1: 0},
            'receiving_tgt': {0: 11, 1: 6},
            'receiving_rec': {0: 10, 1: 2},
            'receiving_yds': {0: 81, 1: 16},
            'receiving_y/r': {0: 8.1, 1: 8.0},
            'receiving_td': {0: 0, 1: 0},
            'receiving_ctch%': {0: '90.9%', 1: '33.3%'},
            'receiving_y/tgt': {0: 7.36, 1: 2.67},
            'passing_cmp': {0: 0, 1: 0},
            'passing_att': {0: 0, 1: 0},
            'passing_cmp%': {0: 0, 1: 0},
            'passing_yds': {0: 0, 1: 0},
            'passing_td': {0: 0, 1: 0},
            'passing_int': {0: 0, 1: 0},
            'passing_rate': {0: 0, 1: 0},
            'passing_sk': {0: 0, 1: 0},
            'passing_yds.1': {0: 0, 1: 0},
            'passing_y/a': {0: 0, 1: 0},
            'passing_ay/a': {0: 0, 1: 0},
            'scoring_2pm': {0: 0, 1: 0},
            'scoring_td': {0: 2, 1: 0},
            'scoring_pts': {0: 12, 1: 0},
            'fumbles_fmb': {0: 0, 1: 0},
            'fumbles_fl': {0: 0, 1: 0},
            'fumbles_ff': {0: 0, 1: 0},
            'fumbles_fr': {0: 0, 1: 0},
            'fumbles_yds': {0: 0, 1: 0},
            'fumbles_td': {0: 0, 1: 0},
            'player_id': {0: 'McCaCh01', 1: 'McCaCh01'},
            'pos': {0: 'RB', 1: 'RB'},
            'year': {0: 2019, 1: 2019},
            'player_name': {0: 'Christian McCaffrey', 1: 'Christian McCaffrey'}
        })

        expected = pd.DataFrame(
            {'player_id': {0: 'McCaCh01', 1: 'McCaCh01'},
            'player_name': {0: 'Christian McCaffrey', 1: 'Christian McCaffrey'},
            'pos': {0: 'RB', 1: 'RB'},
            'year': {0: 2019, 1: 2019},
            'date': {0: '2019-09-08', 1: '2019-09-12'},
            'week': {0: 1.0, 1: 2.0},
            'age': {0: 23.093000000000004, 1: 23.096999999999998},
            'tm': {0: 'CAR', 1: 'CAR'},
            'home/away': {0: 'Home', 1: 'Home'},
            'opp': {0: 'LAR', 1: 'TAM'},
            'result': {0: 'L 27-30', 1: 'L 14-20'},
            'passing_cmp': {0: 0, 1: 0},
            'passing_att': {0: 0, 1: 0},
            'passing_yds': {0: 0, 1: 0},
            'passing_td': {0: 0, 1: 0},
            'passing_int': {0: 0, 1: 0},
            'passing_rate': {0: 0, 1: 0},
            'passing_sk': {0: 0, 1: 0},
            'passing_y/a': {0: 0, 1: 0},
            'passing_ay/a': {0: 0, 1: 0},
            'rushing_att': {0: 19, 1: 16},
            'rushing_yds': {0: 128, 1: 37},
            'rushing_y/a': {0: 6.74, 1: 2.31},
            'rushing_td': {0: 2, 1: 0},
            'receiving_tgt': {0: 11, 1: 6},
            'receiving_rec': {0: 10, 1: 2},
            'receiving_yds': {0: 81, 1: 16},
            'receiving_y/r': {0: 8.1, 1: 8.0},
            'receiving_td': {0: 0, 1: 0},
            'receiving_y/tgt': {0: 7.36, 1: 2.67},
            'scoring_2pm': {0: 0, 1: 0},
            'fumbles': {0: 0, 1: 0},
            'fumbles_lost': {0: 0, 1: 0}}
        )
        assert_frame_equal(expected, player_table_reindex(df))

if __name__ == "__main__":
    unittest.main()
