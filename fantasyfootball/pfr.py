#pfr.py

import pandas as pd
import requests
from bs4 import BeautifulSoup
from os import path

def player_href_list_grab(year):
    """Grabs a list of hrefs for a given year based on descending fantasy performance"""
    url = f'https://www.pro-football-reference.com/years/{year}/fantasy.htm'
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    table = soup.find_all('table')[0]
    a = table.find_all('a')
    href_list = [i.get('href') for i in a if 'players' in str(i)]
    return href_list

def player_id_transform(player_href):
    """Converts a player's href into the last_name_letter and a player_id"""
    last_name_letter = player_href.split('/')[2]
    player_id = player_href.split('/')[3].rsplit('.', 1)[0]
    return last_name_letter, player_id

def player_soup_grab(last_name_letter, player_id, year):
    """Grabs a soup object for week by week fantasy stats""" 
    season_url = f'https://www.pro-football-reference.com/players/{last_name_letter}/{player_id}/gamelog/{year}/'
    r_player = requests.get(season_url)
    soup = BeautifulSoup(r_player.content, 'html.parser')
    return soup

def player_name_and_pos_grab(soup): 
    """Parses a soup object for a player's name and position """ 
    p = soup.find_all('p') 
    for i in p:
        if 'Position' in str(i):
            pos = str(i.get_text()).split()[1]
            break
        else:
            pos = '-'
    player_name = soup.find_all('h1')[0].get_text().rstrip()
    return player_name, pos

def player_table_grab(soup):
    """Grabs the first table in a given soup object and returns a dataframe"""
    player_table = soup.find_all('table')
    df = pd.read_html(str(player_table))[0]
    return df

def player_table_transform(df):
    """transforms a dataframe into a standard fomat"""
    df = df.copy()
    df.drop(columns = ['Off. Snaps', 'Def. Snaps', 'ST Snaps'], level=0, inplace=True)
    df.columns = ['_'.join(col) for col in df.columns]
    df.rename(columns={
                'Unnamed: 6_level_0_Unnamed: 6_level_1': 'home/away',
                'Fumbles_Fmb' : 'fumbles',
                'Fumbles_FL' : 'fumbles_lost'
                }, inplace=True)
    df.columns = [col.lower() for col in df.columns]
    df.columns = [i.split('_')[-1] if 'level' in str(i) else i for i in df.columns]
    df.dropna(subset=['rk'], inplace=True)
    df['home/away'].replace({'@' : 'Away'}, inplace=True)
    df['home/away'].fillna('Home', inplace=True)
    return df

def player_table_variable_add(df, player_id, pos, year, player_name):
    """Adds specific variables as columns in a dataframe"""
    df = df.copy()
    df['player_id'] =  player_id
    df['pos'] =  pos
    df['year'] = year
    df['player_name'] = player_name
    return df

def player_table_reindex(df):
    """Re-orders columns and replaces nans with 0's """
    df = df.copy()
    full_column_List = [
        'player_id', 'player_name', 'pos', 'year', #user-added columns
        'date',  'week', 'age', 'tm', 'home/away', 'opp', 'result',  #standard columns
        'passing_cmp', 'passing_att', 'passing_yds', 'passing_td', 'passing_int', 'passing_rate', 'passing_sk', 'passing_y/a', 'passing_ay/a', #passing columns
        'rushing_att', 'rushing_yds', 'rushing_y/a', 'rushing_td', #rushing columns
        'receiving_tgt', 'receiving_rec', 'receiving_yds', 'receiving_y/r', 'receiving_td', 'receiving_y/tgt', #receiving columns
        'scoring_2pm', #scoring columns
        'fumbles', 'fumbles_lost'    #fumble columns
        ]
    df = df.reindex(columns = full_column_List, fill_value = 0)
    df.fillna(0, inplace=True)
    return df
  
if __name__ == "__main__":
    min = int(input('Minimum year? >>> '))
    max = int(input('Maximum year? >>> '))
    row_n = 300
    DATA_DIR = r'C:\Users\rmull\Documents\Rob\Python Projects\fantasy-football\data\raw'

    df_list = []
    errors_list = []

    for year in range(min, max+1):

        print(f'Grabbing data for {year} ...')

        href_list = player_href_list_grab(year)

        for href in href_list[:row_n]:

            first_letter, player_id = player_id_transform(href)

            try:
                soup = player_soup_grab(first_letter, player_id, year)
                player_name, pos = player_name_and_pos_grab(soup)        
                tdf = player_table_grab(soup)
                tdf = player_table_transform(tdf)
                tdf = player_table_variable_add(tdf, player_id, pos, year, player_name)
                tdf = player_table_reindex(tdf)
                df_list.append(tdf)
            
            except Exception as e:
                # Store the url and the error it causes in a list
                error =[year, href, pos, player_name, e]  
                # then append it to the list of errors
                errors_list.append(error)


    df = pd.concat(df_list)

    rows, cols = df.shape

    df.head()

    df.to_csv(path.join(DATA_DIR, f'Game by Game Breakdown_{min}_{max}.csv'), index=False)

    print(f'All done! The dataframe has {rows} rows and {cols} columns.')

    error_list_len = len(errors_list)

    print(f'There were {error_list_len} errors.\n The error list is: {errors_list}.')
