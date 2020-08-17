# "fantasypros.py"

import pandas as pd
from bs4 import BeautifulSoup
from fantasyfootball.config import DATA_DIR
import requests
from os import path
from datetime import date
import sys
import fantasyfootball.config as config
import fantasyfootball.ffcalculator as ffcalculator
from matplotlib import pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import matplotlib.style as style
from sklearn.mixture import GaussianMixture
import numpy as np
from sklearn.cluster import KMeans

def fantasy_pros_scrape(url):
    """Scrape Fantasy Pros stat projections given a URL"""
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    table = soup.find_all('table', attrs={'id':'data'})
    return pd.read_html(str(table))[0]

def fantasy_pros_column_clean(df):
    """Cleans up columns for Fantasy Pros scraped data tables"""
    df = df.copy()
    df.columns = ['_'.join(col) for col in df.columns]
    df.rename(columns={
                'Unnamed: 0_level_0_Player': 'player_name',
                'RUSHING_TDS' : 'rushing_td',
                'RECEIVING_TDS' : 'receiving_td',
                'PASSING_TDS' : 'passing_td',
                'PASSING_INTS' : 'passing_int',
                'MISC_FL' : 'fumbles',
                'MISC_FPTS' : 'ppr_scoring'
                }, inplace=True)
    df.columns = [col.lower() for col in df.columns]
    df['tm'] = df['player_name'].str.split().str[-1]
    df['player_name'] = df['player_name'].str.rsplit(n=1).str[0]
    df['tm'].replace({'JAC' : 'JAX'}, inplace=True)
    return df

def fantasy_pros_column_reindex(df):
    """Adds columns that are missing from Fantasy Pros tables and reorders columns"""
    full_column_list = [
    'player_name', 'tm', 'pos',
    'receiving_rec', 'receiving_yds', 'receiving_td', 'rushing_att', 'rushing_yds', 'rushing_td', #WR/RB
    'passing_att', 'passing_cmp', 'passing_yds', 'passing_td', 'passing_int', #passing
    'fumbles', 'ppr_scoring'
    ]
    df = df.copy()
    if 'pos' not in df.columns:
        df['pos'] = '-'
    df = df.reindex(columns = full_column_list, fill_value = 0)
    return df

def fantasy_pros_stats_process(url):
    df = fantasy_pros_scrape(url)
    df = fantasy_pros_column_clean(df)
    df = fantasy_pros_column_reindex(df)
    return df

def fantasy_pros_pos_projection_scrape(week='draft', league=config.sean, PPR=True, make_id=False):
    df_list = []
    pos_list = pos_list = ['qb', 'wr', 'te', 'rb']
    for pos in pos_list:
        url = f'https://www.fantasypros.com/nfl/projections/{pos}.php?week=draft&scoring=PPR&week={week}'
        df = fantasy_pros_stats_process(url)
        df['pos'] = pos.upper()
        if not PPR:
            df['standard_scoring'] = df['ppr_scoring'] - df['receiving_rec']
            df.drop(columns=['ppr_scoring'], inplace=True)
        #add custom scoring
        df = config.fantasy_pros_pts(df, league)
        df_list.append(df)
    df = pd.concat(df_list)
    if make_id:                                     
        df = config.unique_id_create(df)
    df.sort_values(f'{league.get("name")}_custom_pts', ascending=False, inplace=True)
    return df

def fantasy_pros_ecr_scrape(league_dict=config.sean):
    """Scrape Fantasy Pros ECR given a league scoring format"""
    scoring = league_dict.get('scoring')
    if scoring == 'ppr':
        url = 'https://www.fantasypros.com/nfl/rankings/ppr-cheatsheets.php'
    elif scoring == 'half-ppr':
        url = 'https://www.fantasypros.com/nfl/rankings/half-point-ppr-cheatsheets.php'
    else:
        url = 'https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php'
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    table = soup.find_all('table')
    return pd.read_html(str(table))[0]

def fantasy_pros_ecr_scrape_column_clean(df):
    """Cleans data for ECR scrape """
    df = df.copy()
    df.columns = [col.lower() for col in df.columns]
    df = (df.drop(columns=['wsid'])
            .dropna(subset=['overall (team)'])
            .rename(columns={'overall (team)' : 'player_name', 'pos' : 'pos_rank'})
         )
    df['rank'] = df['rank'].astype('int')
    df['pos'] = df['pos_rank']
    df['pos'].replace('\d+', '', regex=True, inplace=True)
    df['tm'] = ''
    df.loc[df['pos'] == 'DST', 'tm'] = df.loc[df['pos'] == 'DST', 'player_name'].str.split('(').str[-1].str.split(')').str[0]
    df.loc[df['pos'] != 'DST', 'tm'] = df.loc[df['pos'] != 'DST', 'player_name'].str.split().str[-1]
    df.loc[df['pos'] == 'DST', 'player_name'] = df.loc[df['pos'] == 'DST', 'player_name'].str.rsplit('(', n=1).str[0] + '(' + df['tm'] + ')'
    df.loc[df['pos'] != 'DST', 'player_name'] = df.loc[df['pos'] != 'DST', 'player_name'].str.rsplit(n=1).str[0].str.rsplit(n=1).str[0].str[:-2]
    df['tm'].replace({'JAC' : 'JAX'}, inplace=True)
    df.reset_index(inplace=True, drop=True)
    return df

def fantasy_pros_ecr_column_reindex(df):
    """Reorders columns for ECR data"""
    full_column_list = [
        'rank', 'player_name', 'pos', 'tm', 'pos_rank', 'bye', 'best', 'worst', 'avg', 'std dev',
       'adp', 'vs. adp' 
       ]
    df = df.copy()
    df = df.reindex(columns = full_column_list, fill_value = 0)
    return df

def fantasy_pros_ecr_process(league):
    df = fantasy_pros_ecr_scrape(league)
    df = fantasy_pros_ecr_scrape_column_clean(df)
    df = fantasy_pros_ecr_column_reindex(df)
    return df

def fantasy_pros_ecr_weekly_clean(df):
    """
    Cleans Dfs from FantasyPros weekly rankings
    """
    df = df.copy()
    df.columns = [col.lower() for col in df.columns]
    df = (df.rename(columns={df.columns[2]: 'player_name', 'Rank': 'pos_rank'})
            .drop(columns=['wsis'])
            .dropna(subset=['player_name'])
         )
    df['pos_rank'] = df['pos_rank'].astype('int')
    df['tm'] = df['player_name'].str.split().str[-1]
    #rsplit doesn't support Regex - comment out until bug is fixed
    #df['player_name'] = df['player_name'].str.rsplit('[A-Z]\.').str[0]
    df['player_name'] = df['player_name'].str.rsplit(n=1).str[0].str.rsplit(n=1).str[0].str[:-2]
    df['tm'].replace({'JAC' : 'JAX'}, inplace=True)
    return df

def fantasy_pros_ecr_weekly_scrape(league_dict=config.sean):
    """Scrape Fantasy Pros ECR given a league scoring format (on a week by week basis)"""
    scoring = league_dict.get('scoring')
    pos_list = ['RB', 'WR', 'TE', 'QB', 'K'] #'DST'
    df_list = []
    for pos in pos_list:
        if scoring == 'ppr' and pos in ['RB', 'WR', 'TE']:
            url = f'https://www.fantasypros.com/nfl/rankings/ppr-{pos.lower()}.php'
        elif scoring == 'half-ppr' and pos in ['RB', 'WR', 'TE']:
            url = f'https://www.fantasypros.com/nfl/rankings/half-point-ppr-{pos.lower()}.php'
        else:
            url = f'https://www.fantasypros.com/nfl/rankings/{pos.lower()}.php'
        
        r = requests.get(url)
        soup = BeautifulSoup(r.content, 'html.parser')
        table = soup.find_all('table')
        df = pd.read_html(str(table))[0]
        df['pos'] = pos
        df = fantasy_pros_ecr_weekly_clean(df)
        df_list.append(df)
    df = pd.concat(df_list)
    return df

if __name__ == "__main__":
    pass
    