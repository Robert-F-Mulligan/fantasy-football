#config.py

import pandas as pd
from os import path
import numpy as np

DATA_DIR = r'C:\Users\rmull\Documents\Rob\Python Projects\fantasy-football\data\raw'
FIGURE_DIR = r'C:\Users\rmull\Documents\Rob\Python Projects\fantasy-football\figures'

#scoring systems
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
    'team_n' : 14,
    'scoring' : 'half-ppr',
    'rounds' : 15-2,
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

def fantasy_pros_pts(my_df, my_dict):
    """Adds a column to a dataframe for fantasy points based on custom league specs for Fantasy Pros Projections"""
    my_df = my_df.copy()
    my_df[f'{my_dict.get("name")}_custom_pts'] = (
      my_df['receiving_rec'] * my_dict.get('receiving_rec')  
      + my_df['receiving_yds'] * my_dict.get('receiving_yds')
      + my_df['receiving_td'] * my_dict.get('receiving_td')
      + my_df['rushing_yds'] * my_dict.get('rushing_yds')
      + my_df['rushing_td'] * my_dict.get('rushing_td')
      + my_df['passing_yds'] * my_dict.get('passing_yds')
      + my_df['passing_td'] * my_dict.get('passing_td')
      + my_df['passing_int'] * my_dict.get('passing_int')
      + my_df['fumbles'] * my_dict.get('fumbles')
    )
    return my_df

def pro_football_reference_pts(my_df, my_dict):
    """Adds a column to a dataframe for fantasy points based on custom league specs for Pro Football Reference data"""
    my_df = my_df.copy()
    my_df[f'{my_dict.get("name")}_custom_pts'] = (
      my_df['receiving_rec'] * my_dict.get('receiving_rec')  
      + my_df['receiving_yds'] * my_dict.get('receiving_yds')
      + my_df['receiving_td'] * my_dict.get('receiving_td')
      + my_df['rushing_yds'] * my_dict.get('rushing_yds')
      + my_df['rushing_td'] * my_dict.get('rushing_td')
      + my_df['passing_yds'] * my_dict.get('passing_yds')
      + my_df['passing_td'] * my_dict.get('passing_td')
      + my_df['passing_int'] * my_dict.get('passing_int')
      + my_df['fumbles'] * my_dict.get('fumbles')
      + my_df['fumbles_lost'] * my_dict.get('fumbles_lost')          
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
def value_over_last_starter(my_df, my_dict, pos_list):
    """Calculates the value for a low-end starter, given a datframe, league dict and pos list"""
    replacement_value = {}
    my_df = my_df.copy()
    my_df.sort_values('adp', inplace=True)
    for pos in pos_list:
        pos_cutoff = my_dict.get(pos) * my_dict.get('team_n')
        tdf = my_df.loc[my_df['pos'] == pos.upper(), [f'{my_dict.get("name")}_custom_pts']]
        tdf = tdf.head(pos_cutoff)
        replacement_value[pos.upper()] = float(np.mean(tdf.tail(3)))
    return replacement_value

def value_over_avg_starter(my_df, my_dict, pos_list):
    """Calculates the avg output for a starter, given a daatframe, league dict and pos list"""
    replacement_value = {}
    my_df = my_df.copy()
    my_df.sort_values('adp', inplace=True)
    for pos in pos_list:
        pos_cutoff = my_dict.get(pos) * my_dict.get('team_n')
        tdf = my_df.loc[my_df['pos'] == pos.upper(), [f'{my_dict.get("name")}_custom_pts']]
        tdf = tdf.head(pos_cutoff)
        replacement_value[pos.upper()] = float(np.mean(tdf))
    return replacement_value

def value_over_replacement_player(my_df, my_dict, pos_list):
    """Calculates the replacement value for a starter, given a datframe, league dict and pos list"""
    replacement_value = {}
    my_df = my_df.copy()
    my_df.sort_values('adp', inplace=True)
    for pos in pos_list:
        draft_cutoff = my_dict.get('rounds') * my_dict.get('team_n')
        tdf = my_df.head(draft_cutoff)
        tdf = tdf.loc[my_df['pos'] == pos.upper(), [f'{my_dict.get("name")}_custom_pts']]
        replacement_value[pos.upper()] = float(np.mean(tdf.tail(3)))
    return replacement_value

def value_through_n_picks(my_df, my_dict, pos_list, pick_n=125):
    """Calculates the value per pos through 100 picks, given a datframe, league dict and pos list"""
    replacement_value = {}
    my_df = my_df.copy()
    my_df.sort_values('adp', inplace=True)
    my_df.reset_index(inplace=True, drop=True)
    my_df = my_df.head(pick_n)
    for pos in pos_list:
        tdf = my_df.loc[my_df['pos'] == pos.upper(), [f'{my_dict.get("name")}_custom_pts']]
        replacement_value[pos.upper()] = float(np.mean(tdf.tail(1)))
    return replacement_value


#team abbreviation dicts
pfr_to_fantpros = {
    'ARI':'ARI',
    'ATL':'ATL',
    'BAL':'BAL',
    'BUF':'BUF',
    'CAR':'CAR',
    'CHI':'CHI',
    'CIN':'CIN',
    'CLE':'CLE',
    'DAL':'DAL',
    'DEN':'DEN',
    'DET':'DET',
    'GNB':'GB',
    'HOU':'HOU',
    'IND':'IND',
    'JAX':'JAX',
    'KAN':'KC',
    'LAC':'LAC',
    'LAR':'LAR',
    'OAK':'LV',
    'MIA':'MIA',
    'MIN':'MIN',
    'NWE':'NE',
    'NOR':'NO',
    'NYG':'NYG',
    'NYJ':'NYJ',
    'PHI':'PHI',
    'PIT':'PIT',
    'SEA':'SEA',
    'SFO':'SF',
    'TAM':'TB',
    'TEN':'TEN',
    'WAS':'WAS'
    }

fantpros_to_pfcalc= {
    'ARI':'ARI',
    'ATL': 'ATL',
    'BAL':'BAL',
    'BUF':'BUF',
    'CAR':'CAR',
    'CHI':'CHI',
    'CIN':'CIN',
    'CLE':'CLE',
    'DAL':'DAL',
    'DEN':'DEN',
    'DET':'DET',
    'GB':'GB',
    'HOU':'HOU',
    'IND':'IND',
    'JAC':'JAX',
    'KC':'KC',
    'LAC':'LAC',
    'LAR':'LAR',
    'LV':'LV',
    'MIA':'MIA',
    'MIN':'MIN',
    'NE':'NE',
    'NO':'NO',
    'NYG':'NYG',
    'NYJ':'NYJ',
    'PHI':'PHI',
    'PIT':'PIT',
    'SEA':'SEA',
    'SF':'SF',
    'TB':'TB',
    'TEN':'TEN',
    'WAS':'WAS'
    }
