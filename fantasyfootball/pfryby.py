# pfryby.py

import pandas as pd
import requests
from bs4 import BeautifulSoup
from os import path
from fantasyfootball.config import DATA_DIR

def pfr_year_by_year_table_grab(year):
    """Grabs fantasy stats for a given year """
    url = f'https://www.pro-football-reference.com/years/{year}/fantasy.htm'
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    player_table = soup.find_all('table')
    df = pd.read_html(str(player_table))[0]
    df['year'] = year
    return df

def year_by_year_player_table_transform(df):
    """transforms a dataframe into a standard fomat"""
    df = df.copy()
    df.drop(columns = ['FantPt','PPR', 'DKPt', 'FDPt', 'VBD'], level=1, inplace=True)
    df.columns = ['_'.join(col) for col in df.columns]
    df.columns = [col.lower() for col in df.columns]
    df.columns = [i.split('_')[-1] if 'level' in str(i) else i for i in df.columns]
    df = df.loc[df['rk'] != 'Rk']
    df.rename(columns={
                'player': 'player_name',
                'fumbles_fmb' : 'fumbles',
                'fumbles_fl' : 'fumbles_lost',
                'games_g' : 'games',
                'games_gs' : 'games_started',
                'fantpos' : 'pos',
                'year_' : 'year'
                }, inplace=True)
    df['player_name'] = df['player_name'].str.split('*').str[0].str.split('+').str[0]
    return df

def year_by_year_player_table_reindex(df):
    """Re-orders columns and replaces nans with 0's """
    df = df.copy()
    full_column_List = [
        'rk', 'player_name', 'pos', 'year', 
        'age', 'tm',  'games', 'games_started',
        'passing_cmp', 'passing_att', 'passing_yds', 'passing_td', 'passing_int',
        'rushing_att', 'rushing_yds', 'rushing_y/a', 'rushing_td', #rushing columns
        'receiving_tgt', 'receiving_rec', 'receiving_yds', 'receiving_y/r', 'receiving_td',
        'scoring_2pm', #scoring columns
        'fumbles', 'fumbles_lost',    #fumble columns
        'fantasy_posrank', 'fantasy_ovrank'
        ]
    df = df.reindex(columns = full_column_List, fill_value = 0)
    df.fillna(0, inplace=True)
    return df



if __name__ == "__main__":
    min = int(input('Minimum year? >>> '))
    max = int(input('Maximum year? >>> '))

    for year in range(min, max+1):
        df = pfr_year_by_year_table_grab(year)
        df = year_by_year_player_table_transform(df)
        df = year_by_year_player_table_reindex(df)

        df.to_csv(path.join(DATA_DIR,fr'year-by-year\{year}.csv'), index=False)