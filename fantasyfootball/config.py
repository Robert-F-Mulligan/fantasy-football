#config.py

import pandas as pd
from os import path
import numpy as np

DATA_DIR = r'..\data'
FIGURE_DIR = r'..\figures'

#scoring systems
ppr = {
    'name' : 'ppr',
    'team_n' : 12, 
    'scoring' : 'ppr',
    'rounds' : 15-2,
    'passing_yds' : 0.04,
    'passing_td' : 6,
    'passing_int' : -1,
    'rushing_yds' : 0.1,
    'rushing_td' : 6,
    'receiving_rec' : 1,
    'receiving_yds' : 0.1,
    'receiving_td' : 6,
    'fumbles' : -1,
    'fumbles_lost' : -2,
    'qb' : 1,
    'rb' : 2,
    'wr' : 2,
    'te' : 1,
    'flex' : 1,
    'dst' : 1,
    'k' : 1
}
justin = {
    'name' : 'justin',
    'team_n' : 12,
    'scoring' : 'ppr',
    'rounds' : 16-2,
    'passing_yds' : 0.05,
    'passing_td' : 6,
    'passing_int' : -3,
    'rushing_yds' : 0.1,
    'rushing_td' : 6,
    'receiving_rec' : 1,
    'receiving_yds' : 0.1,
    'receiving_td' : 6,
    'fumbles' : 0,
    'fumbles_lost' : -3,
    'qb' : 1,
    'rb' : 2,
    'wr' : 2,
    'te' : 1,
    'flex' : 1,
    'dst' : 1,
    'k' : 1
}

sean = {
    'name' : 'sean',
    'team_n' : 12, 
    'scoring' : 'ppr',
    'rounds' : 15-2,
    'passing_yds' : 0.04,
    'passing_td' : 6,
    'passing_int' : -1,
    'rushing_yds' : 0.1,
    'rushing_td' : 6,
    'receiving_rec' : 1,
    'receiving_yds' : 0.1,
    'receiving_td' : 6,
    'fumbles' : -1,
    'fumbles_lost' : -2,
    'qb' : 1,
    'rb' : 2,
    'wr' : 2,
    'te' : 1,
    'flex' : 1,
    'dst' : 1,
    'k' : 1
}

work = {
    'name' : 'work',
    'team_n' : 10, #2020 season changed from 14 to 10
    'scoring' : 'half-ppr',
    'rounds' : 17-2, #bench was increased to 8 for covid
    'passing_yds' : 0.02857143,
    'passing_td' : 5,
    'passing_int' : -2,
    'rushing_yds' : 0.1,
    'rushing_td' : 6,
    'receiving_rec' : 0.5,
    'receiving_yds' : 0.1,
    'receiving_td' : 6,
    'fumbles' : 0,
    'fumbles_lost' : -2,
    'qb' : 1,
    'rb' : 1,
    'wr' : 2,
    'te' : 1,
    'flex' : 2,
    'dst' : 1,
    'k' : 1
}

scoring_List = [sean, justin, work]

def fantasy_pros_pts(my_df, my_dict=ppr):
    """Adds a column to a dataframe for fantasy points based on custom league specs for Fantasy Pros Projections"""
    my_df = my_df.copy()
    my_df[f'{my_dict["name"]}_custom_pts'] = (
      my_df['receiving_rec'] * my_dict['receiving_rec']
      + my_df['receiving_yds'] * my_dict['receiving_yds']
      + my_df['receiving_td'] * my_dict['receiving_td']
      + my_df['rushing_yds'] * my_dict['rushing_yds']
      + my_df['rushing_td'] * my_dict['rushing_td']
      + my_df['passing_yds'] * my_dict['passing_yds']
      + my_df['passing_td'] * my_dict['passing_td']
      + my_df['passing_int'] * my_dict['passing_int']
      + my_df['fumbles'] * my_dict['fumbles']
    )
    return my_df

def pro_football_reference_pts(my_df, my_dict=ppr):
    """Adds a column to a dataframe for fantasy points based on custom league specs for Pro Football Reference data"""
    my_df = my_df.copy()
    my_df[f'{my_dict["name"]}_custom_pts'] = (
      my_df['receiving_rec'] * my_dict['receiving_rec']
      + my_df['receiving_yds'] * my_dict['receiving_yds']
      + my_df['receiving_td'] * my_dict['receiving_td']
      + my_df['rushing_yds'] * my_dict['rushing_yds']
      + my_df['rushing_td'] * my_dict['rushing_td']
      + my_df['passing_yds'] * my_dict['passing_yds']
      + my_df['passing_td'] * my_dict['passing_td']
      + my_df['passing_int'] * my_dict['passing_int']
      + my_df['fumbles'] * my_dict['fumbles']
      + my_df['fumbles_lost'] * my_dict['fumbles_lost']
    )
    return my_df


def unique_id_create(my_df, team=False):
    """Derives a unique ID to allow for merges across different data sources"""
    my_df = my_df.copy()
    char_list = ["'", ' III', ' II', ' IV', ' V', 'Jr',  '\.', '-'] #removed ' '
    symbol_dict = dict(zip(char_list, len(char_list)*['']))
    if team:
        my_df = (my_df.assign(id = (
                          my_df['player_name'].replace(symbol_dict, regex=True)
                                              .str.lower()
                                              .str.split()
                                              .str[0].str[0:3]
                         + '_' 
                         + my_df['player_name'].replace(symbol_dict, regex=True)
                                               .str.lower()
                                               .str.split()
                                               .str[1]
                         + '_' 
                         + my_df['pos']
                         + '_' 
                         + my_df['tm']
                               ).str.lower())
                )
    else:            
        my_df = (my_df.assign(id = (
                           my_df['player_name'].replace(symbol_dict, regex=True)
                                                .str.lower()
                                                .str.split()
                                                .str[0].str[0:3]
                         + '_' 
                          + my_df['player_name'].replace(symbol_dict, regex=True)
                                                .str.lower()
                                                .str.split()
                                                .str[1]
                         + '_' 
                         + my_df['pos']
                               ).str.lower())
                )
    return my_df

#VBD functions
def value_over_last_starter(my_df, pos_list, my_dict=ppr):
    """Calculates the value for a low-end starter, given a datframe, league dict and pos list"""
    replacement_value = {}
    my_df = my_df.copy()
    my_df.sort_values('adp', inplace=True)
    for pos in pos_list:
        pos_cutoff = my_dict[pos] * my_dict['team_n']
        tdf = my_df.loc[my_df['pos'] == pos.upper(), [f'{my_dict["name"]}_custom_pts']]
        tdf = tdf.head(pos_cutoff)
        replacement_value[pos.upper()] = float(np.mean(tdf.tail(3)))
    return replacement_value

def value_over_avg_starter(my_df, pos_list, my_dict=ppr):
    """Calculates the avg output for a starter, given a daatframe, league dict and pos list"""
    replacement_value = {}
    my_df = my_df.copy()
    my_df.sort_values('adp', inplace=True)
    for pos in pos_list:
        pos_cutoff = my_dict[pos] * my_dict['team_n']
        tdf = my_df.loc[my_df['pos'] == pos.upper(), [f'{my_dict["name"]}_custom_pts']]
        tdf = tdf.head(pos_cutoff)
        replacement_value[pos.upper()] = float(np.mean(tdf))
    return replacement_value

def value_over_replacement_player(my_df, pos_list, my_dict=ppr):
    """Calculates the replacement value for a starter, given a datframe, league dict and pos list"""
    replacement_value = {}
    my_df = my_df.copy()
    my_df.sort_values('adp', inplace=True)
    for pos in pos_list:
        draft_cutoff = my_dict['rounds'] * my_dict['team_n']
        tdf = my_df.head(draft_cutoff)
        tdf = tdf.loc[my_df['pos'] == pos.upper(), [f'{my_dict["name"]}_custom_pts']]
        replacement_value[pos.upper()] = float(np.mean(tdf.tail(3)))
    return replacement_value

def value_through_n_picks(my_df, pos_list,  my_dict=ppr):
    """Calculates the value per pos through 100 picks, given a datframe, league dict and pos list"""
    replacement_value = {}
    pick_dict = {10: 100, 12: 120, 14: 140}
    pick_n = pick_dict.get(my_dict['team_n'], 100)
    my_df = my_df.copy()
    my_df.sort_values('adp', inplace=True)
    my_df.reset_index(inplace=True, drop=True)
    my_df = my_df.head(pick_n)
    for pos in pos_list:
        tdf = my_df.loc[my_df['pos'] == pos.upper(), [f'{my_dict["name"]}_custom_pts']]
        replacement_value[pos.upper()] = float(np.mean(tdf.tail(1)))
    return replacement_value


#team abbreviation dicts
pfr_to_fantpros = {
    'GNB':'GB',
    'KAN':'KC',
    'LVR':'LV',
    'NWE':'NE',
    'NOR':'NO',
    'SFO':'SF',
    'TAM':'TB',
    }


nfl_color_map = {
'ARI': '#97233F',
 'ATL': '#A71930',
 'BAL': '#241773',
 'BUF': '#00338D',
 'CAR': '#0085CA',
 'CHI': '#0B162A',
 'CIN': '#FB4F14',
 'CLE': '#311D00',
 'DAL': '#041E42',
 'DEN': '#FB4F14',
 'DET': '#0076B6',
 'GB': '#203731',
 'HOU': '#03202F',
 'IND': '#002C5F',
 'JAX': '#006778',
 'KC': '#E31837',
 'LAC': '#0080C6',
 'LAR': '#003594',
 'LA': '#003594',
 'LV': '#000000',
 'MIA': '#008E97',
 'MIN': '#4F2683',
 'NE': '#B0B7BC',
 'NO': '#D3BC8D',
 'NYG': '#0B2265',
 'NYJ': '#125740',
 'PHI': '#004C54', 
 'PIT': '#FFB612',
 'SF': '#B3995D',
 'SEA': '#69BE28',
 'TB': '#D50A0A',
 'TEN': '#4B92DB',
 'WAS': '#773141'
}

nfl_logo_map_web = {
'ARI': 'https://content.sportslogos.net/logos/7/177/full/kwth8f1cfa2sch5xhjjfaof90.png',
'ATL': 'https://content.sportslogos.net/logos/7/173/full/299.png',
 'BAL': 'https://content.sportslogos.net/logos/7/153/full/318.png',
 'BUF': 'https://content.sportslogos.net/logos/7/149/full/n0fd1z6xmhigb0eej3323ebwq.png',
 'CAR': 'https://content.sportslogos.net/logos/7/174/full/f1wggq2k8ql88fe33jzhw641u.png',
 'CHI': 'https://content.sportslogos.net/logos/7/169/full/364.png',
 'CIN': 'https://content.sportslogos.net/logos/7/154/full/403.png',
 'CLE': 'https://content.sportslogos.net/logos/7/155/full/7855_cleveland_browns-primary-2015.png',
 'DAL': 'https://content.sportslogos.net/logos/7/165/full/406.png',
 'DEN': 'https://content.sportslogos.net/logos/7/161/full/9ebzja2zfeigaziee8y605aqp.png',
 'DET': 'https://content.sportslogos.net/logos/7/170/full/1398_detroit_lions-primary-2017.png',
 'GB': 'https://content.sportslogos.net/logos/7/171/full/dcy03myfhffbki5d7il3.png',
 'HOU': 'https://content.sportslogos.net/logos/7/157/full/570.png',
 'IND': 'https://content.sportslogos.net/logos/7/158/full/593.png',
 'JAX': 'https://content.sportslogos.net/logos/7/159/full/8856_jacksonville_jaguars-alternate-2013.png',
 'KC': 'https://content.sportslogos.net/logos/7/162/full/857.png',
 'LAC': 'https://content.sportslogos.net/logos/7/6446/full/1660_los_angeles__chargers-primary-20201.png',
 'LAR': 'https://content.sportslogos.net/logos/7/5941/full/8334_los_angeles_rams-primary-20201.png',
 'LV': 'https://content.sportslogos.net/logos/7/6708/full/8521_las_vegas_raiders-primary-20201.png',
 'MIA': 'https://content.sportslogos.net/logos/7/150/full/7306_miami_dolphins-primary-2018.png',
 'MIN': 'https://content.sportslogos.net/logos/7/172/full/2704_minnesota_vikings-primary-20131.png',
 'NE': 'https://content.sportslogos.net/logos/7/151/full/y71myf8mlwlk8lbgagh3fd5e0.png',
 'NO': 'https://content.sportslogos.net/logos/7/175/full/907.png',
 'NYG': 'https://content.sportslogos.net/logos/7/166/full/919.gif',
 'NYJ': 'https://content.sportslogos.net/logos/7/152/full/9116_new_york_jets-primary-2019.png',
 'PHI': 'https://content.sportslogos.net/logos/7/167/full/960.png', 
 'PIT': 'https://content.sportslogos.net/logos/7/156/full/970.png',
 'SF': 'https://content.sportslogos.net/logos/7/179/full/9455_san_francisco_49ers-primary-2009.png',
 'SEA': 'https://content.sportslogos.net/logos/7/180/full/pfiobtreaq7j0pzvadktsc6jv.png',
 'TB': 'https://content.sportslogos.net/logos/7/176/full/8363_tampa_bay_buccaneers-primary-2020.png',
 'TEN': 'https://content.sportslogos.net/logos/7/160/full/1053.png',
 'WAS': 'https://content.sportslogos.net/logos/7/6741/full/8837_washington_football_team-wordmark-20201.png'
}

nfl_logo_map_wiki = {
 'ARI': 'Arizona_Cardinals_logo.png',
 'ATL': 'Atlanta_Falcons_logo.png',
 'BAL': 'Baltimore_Ravens_logo.png',
 'BUF': 'Buffalo_Bills_logo.png',
 'CAR': 'Carolina_Panthers_logo.png',
 'CHI': 'Chicago_Bears_logo.png',
 'CIN': 'Cincinnati_Bengals_logo.png',
 'CLE': 'Cleveland_Browns_logo.png',
 'DAL': 'Dallas_Cowboys_logo.png',
 'DEN': 'Denver_Broncos_logo.png',
 'DET': 'Detroit_Lions_logo.png',
 'GB': 'Green_Bay_Packers_logo.png',
 'HOU': 'Houston_Texans_logo.png',
 'IND': 'Indianapolis_Colts_logo.png',
 'JAX': 'Jacksonville_Jaguars_logo.png',
 'KC': 'Kansas_City_Chiefs_logo.png',
 'LAC': 'Los_Angeles_Chargers_logo.png',
 'LAR': 'Los_Angeles_Rams_logo..png',
 'LV':  'Las_Vegas_Raiders_logo.png',
 'MIA': 'Miami_Dolphins_logo.png',
 'MIN': 'Minnesota_Vikings_logo.png',
 'NE': 'New_England_Patriots_logo.png',
 'NO': 'New_Orleans_Saints_logo.png',
 'NYG': 'New_York_Giants_logo.png',
 'NYJ': 'New_York_Jets_logo.png',
 'PHI': 'Philadelphia_Eagles_logo.png',
 'PIT': 'Pittsburgh_Steelers_logo.png',
 'SF': 'San_Francisco_49ers_logo.png',
 'SEA': 'Seattle_Seahawks_logo.png',
 'TB': 'Tampa_Bay_Buccaneers_logo.png',
 'TEN': 'Tennessee_Titans_logo.png',
 'WAS': 'Washington_Football_Team_logo.png'
 }

nfl_logo_map_espn = {
    'ARI': 'ARI.png',
    'ATL': 'ATL.png',
    'BAL': 'BAL.png',
    'BUF': 'BUF.png',
    'CAR': 'CAR.png',
    'CHI': 'CHI.png',
    'CIN': 'CIN.png',
    'CLE': 'CLE.png',
    'DAL': 'DAL.png',
    'DEN': 'DEN.png',
    'DET': 'DET.png',
    'GB': 'GB.png',
    'HOU': 'HOU.png',
    'IND': 'IND.png',
    'JAX': 'JAX.png',
    'KC': 'KC.png',
    'LAC': 'LAC.png',
    'LA': 'LAR.png',
    'LAR': 'LAR.png',
    'LV': 'LV.png',
    'MIA': 'MIA.png',
    'MIN': 'MIN.png',
    'NE': 'NE.png',
    'NO': 'NO.png',
    'NYG': 'NYG.png',
    'NYJ': 'NYJ.png',
    'PHI': 'PHI.png',
    'PIT': 'PIT.png',
    'SF': 'SF.png',
    'SEA': 'SEA.png',
    'TB': 'TB.png',
    'TEN': 'TEN.png',
    'WAS': 'WAS.png',
    'NFL': 'NFL.png'
    }

WIKI_DIR = r'..\figures\logos\wikipedia'
ESPN_DIR = r'..\figures\logos\espn'

nfl_logo_png_path_map = {team: path.join(WIKI_DIR,filename) for team, filename in nfl_logo_map_wiki.items()}
nfl_logo_espn_path_map = {team: path.join(ESPN_DIR,filename) for team, filename in nfl_logo_map_espn.items()}