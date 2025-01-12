# "fantasypros.py"

import pandas as pd
from bs4 import BeautifulSoup
from fantasyfootball.config import DATA_DIR, DRIVER_PATH
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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import json
import re
from time import sleep

def fantasy_pros_scrape(url):
    """Scrape Fantasy Pros stat projections
    
    :param url: url where data will be scraped from
    """
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    table = soup.find_all('table', attrs={'id':'data'})
    return pd.read_html(str(table))[0]

def fantasy_pros_column_clean(df):
    """Cleans up columns for Fantasy Pros scraped data tables
    
    :param df: dataframe object that has been scraped from a url
    """
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
    """Adds columns that are missing from Fantasy Pros tables and reorders columns
       Some tables are missing stats (no passing stats for RBs) so this will fill in the gaps and
       have '0' as the value for any missing column
    
    :param df: cleaned dataframe object resulting from a web scrape
    """
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
    """This function scrapes projected stats for each player across each skill position

    :param week: week of season to scrape
    :param league: league dict in config.py used to determine scoring rules
    :param PPR: flag to include PPR or standard scoring columns in the resultant dataframe
    :param made_id: flag to include a unique ID column that can be used to join to another dataframe
    """
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
    """Scrape Fantasy Pros ECR given a league scoring format
    
    :param league_dict: league dict in config.py used to determine whether to pull PPR/standard/half-ppr
    """
    scoring = league_dict.get('scoring')
    if scoring == 'ppr':
        url = 'https://www.fantasypros.com/nfl/rankings/ppr-cheatsheets.php'
    elif scoring == 'half-ppr':
        url = 'https://www.fantasypros.com/nfl/rankings/half-point-ppr-cheatsheets.php'
    else:
        url = 'https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php'
    html = scrape_dynamic_javascript(url)
    parsed_dict = parse_ecr_html(html)
    return pd.DataFrame(parsed_dict)

def fantasy_pros_ecr_scrape_column_clean(df):
    """Cleans data for ECR scrape
    
    :param df: dataframe object that has been scraped from a url
    """
    df = df.copy()
    ecr_col = {
    'rank_ecr': 'rank',
    'player_name': 'player_name',
    'player_team_id': 'tm',
    'pos_rank': 'pos_rank',
    'player_positions': 'pos',
    'player_bye_week': 'bye',
    'rank_min': 'best',
   'rank_max': 'worst',
    'rank_ave': 'avg',
    'rank_std': 'std dev'
    }
    df = df.rename(columns=ecr_col)
    df['tm'].replace({'JAC' : 'JAX'}, inplace=True)
    df.reset_index(inplace=True, drop=True)
    return df

def fantasy_pros_ecr_column_reindex(df):
    """Reorders columns for ECR data
    
    :param df: cleaned dataframe object resulting from a web scrape
    """
    full_column_list = [
        'rank', 'player_name', 'pos', 'tm', 'pos_rank', 'bye', 'best', 'worst', 'avg', 'std dev' 
       ]
    df = df.copy()
    df = df.reindex(columns = full_column_list, fill_value = 0)
    return df

def fantasy_pros_ecr_process(league):
    df = fantasy_pros_ecr_scrape(league)
    df = fantasy_pros_ecr_scrape_column_clean(df)
    df = fantasy_pros_ecr_column_reindex(df)
    return df

def scrape_dynamic_javascript(url):
    options = Options()
    options.headless = True
    #options.add_argument("--window-size=1920,1200")
    options.add_argument("--log-level=3") #suppress non-fatal logs

    driver = webdriver.Chrome(options=options, executable_path=DRIVER_PATH)
    driver.get(url)
    sleep(5)
    html = driver.execute_script("return document.getElementsByTagName('html')[0].innerHTML")
    driver.quit()
    return html

def parse_ecr_html(html):
    values = re.findall(r'var ecrData.*?=\s*(.*?)\s*var\ssosData', html, re.DOTALL | re.MULTILINE)
    parsed_dict = json.loads(values[0][:-1])
    return parsed_dict['players']

def parse_sos_html(html):
    values = re.findall(r'var sosData.*?=\s*(.*?)\s*var\sadpData', html, re.DOTALL | re.MULTILINE)
    parsed_dict = json.loads(values[0][:-1])
    return pd.DataFrame(parsed_dict).T

def fantasy_pros_ecr_weekly_scrape(league_dict=config.sean):
    """Scrape Fantasy Pros ECR given a league scoring format (on a week by week basis)
    
    :param league_dict: league dict in config.py used to determine whether to pull PPR/standard/half-ppr
    """
    scoring = league_dict['scoring']
    pos_list = ['RB', 'WR', 'TE', 'QB', 'K', 'DST','FLEX']
    df_list = []
    for pos in pos_list:
        if scoring == 'ppr' and pos in ['RB', 'WR', 'TE']:
            url = f'https://www.fantasypros.com/nfl/rankings/ppr-{pos.lower()}.php'
        elif scoring == 'half-ppr' and pos in ['RB', 'WR', 'TE']:
            url = f'https://www.fantasypros.com/nfl/rankings/half-point-ppr-{pos.lower()}.php'
        else:
            url = f'https://www.fantasypros.com/nfl/rankings/{pos.lower()}.php'
        
        html = scrape_dynamic_javascript(url)
        parsed_dict = parse_ecr_html(html)
        df = pd.DataFrame(parsed_dict)
        #Flex and pos have different columns
        if pos == 'FLEX':
            df['r2p_pts'] = np.nan
        df['pos'] = pos
        df_list.append(df)
    df = pd.concat(df_list)
    proj_pts_df = df[['player_name', 'r2p_pts']].dropna(subset=['r2p_pts'])
    pts_map = dict(zip(proj_pts_df['player_name'].to_list(), proj_pts_df['r2p_pts'].to_list()))
    df['r2p_pts'] = df['player_name'].map(pts_map)
    return df

def fantasy_pros_ecr_weekly_transform(df):
    df = df.copy()
    float_cols = ['best', 'worst', 'avg', 'std dev','proj. pts']
    col_map = {
        'rank_ecr': 'rank',
        'player_name': 'player_name',
        'player_opponent': 'opp',
        'rank_min': 'best',
        'rank_max': 'worst',
        'rank_ave': 'avg',
        'rank_std': 'std dev',
        'r2p_pts': 'proj. pts',
        'pos': 'pos',
        'pos_rank': 'pos_rank',
        'player_team_id': 'tm'
        }
    df = df.rename(columns=col_map)
    df[float_cols] = df[float_cols].astype('float')
    return df.loc[:, [v for _, v in col_map.items()] + ['start_sit_grade']]

def create_fantasy_pros_ecr_df(league_dict=config.sean):
    df = (fantasy_pros_ecr_weekly_scrape(league_dict)
            .pipe(fantasy_pros_ecr_weekly_transform))
    return df

if __name__ == "__main__":
    pass
    