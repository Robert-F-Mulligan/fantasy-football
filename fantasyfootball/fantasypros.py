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
    'id', 'player_name', 'tm', 'pos',
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
    df.drop(columns=['wsid'], inplace=True)
    df.dropna(subset=['overall (team)'], inplace=True)
    df['rank'] = df['rank'].astype('int')
    df.rename(columns={
    'overall (team)' : 'player_name',
    'pos' : 'pos_rank'
            }, inplace=True)
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

if __name__ == "__main__":

    league = config.sean
    pos_list = ['qb', 'wr', 'te', 'rb']
    today = date.today()
    date = today.strftime('%Y.%m.%d')
    weekly_stats = pd.read_csv(path.join(DATA_DIR, r'game-by-game\2019_weekly.csv'))
    errors_list = []
    try:
        print('Pulling in position projections...')
        df_list = []
        for pos in pos_list:
            url = f'https://www.fantasypros.com/nfl/projections/{pos}.php?week=draft&scoring=PPR&week=draft'
            scraped_df = fantasy_pros_scrape(url)
            cleaned_df = fantasy_pros_column_clean(scraped_df)
            cleaned_df['pos'] = pos.upper()
            cleaned_df = config.unique_id_create(cleaned_df, 'player_name', 'pos', 'tm')
            cleaned_df = config.char_replace(cleaned_df, 'id')
            cleaned_reindexed_df = fantasy_pros_column_reindex(cleaned_df)
            cleaned_reindexed_df['std_scoring'] = cleaned_reindexed_df['ppr_scoring'] - cleaned_reindexed_df['receiving_rec']
            cleaned_reindexed_df['half_ppr_scoring'] = cleaned_reindexed_df['ppr_scoring'] - 0.5*cleaned_reindexed_df['receiving_rec']
            cleaned_reindexed_df = config.fantasy_pros_pts(cleaned_reindexed_df, league)
            df_list.append(cleaned_reindexed_df)
        fantasy_pros_df = pd.concat(df_list)
        fantasy_pros_df.sort_values(f'{league.get("name")}_custom_pts', ascending=False, inplace=True)

    except Exception as e:
        # Store the url and the error it causes in a list
        error =[e]  
        # then append it to the list of errors
        errors_list.append(error)

    print('Pulling in ADP...')

    adp_df = ffcalculator.adp_scrape(league)
    adp_df = ffcalculator.adp_column_clean(adp_df, league)

    #combines DFs
    merged_df = fantasy_pros_df.merge(adp_df, how='left', on='id').sort_values('adp').reset_index(drop=True)
    merged_df.drop(columns=['name', 'pos_y', 'team', 'id'], inplace=True)
    merged_df.rename(columns={'pos_x' : 'pos'}, inplace=True)


    #create new id for previous season aggs
    merged_df = config.unique_id_create(merged_df, 'player_name', 'pos')
    merged_df = config.char_replace(merged_df, 'id')

    #import last season aggs
    print("Grabbing last season's aggs...")                   
    weekly_stats.columns = [col.lower() for col in weekly_stats.columns]

    #new id omits team name to prevent players with new teams from breaking the merge
    weekly_stats = config.unique_id_create(weekly_stats, 'player_name', 'pos')
    year = weekly_stats['year'].max()
    weekly_stats = config.char_replace(weekly_stats, 'id')
    weekly_stats = config.pro_football_reference_pts(weekly_stats, league)
    agg_df = weekly_stats.groupby('id').agg(
        avg_ppg =(f'{league.get("name")}_custom_pts', 'mean'),
        std_dev=(f'{league.get("name")}_custom_pts', 'std')
        )
    agg_df.rename(columns={'avg_ppg' : f'{year}_avg_ppg', 'std_dev' : f'{year}_std_dev'}, inplace=True)

    merged_df = merged_df.merge(agg_df, how='left', on='id').reset_index(drop=True)
    merged_df.drop(columns=['id'], inplace=True)


    #run the desired VBD function to calculate replacement player
    replacement_value = config.value_through_n_picks(merged_df, league, pos_list)

    #map replacement value to df and calculate value above replacement
    print('Mapping VBD...')
    merged_df[f'{league.get("name")}_custom_pts_vor'] = merged_df[f'{league.get("name")}_custom_pts'] - merged_df['pos'].map(replacement_value)
    merged_df.sort_values(f'{league.get("name")}_custom_pts_vor', inplace=True, ascending=False)
    merged_df.reset_index(drop=True)

    #export to CSVs
    merged_df[['player_name', 'tm', 'pos', 'bye', 'adp', f'{year}_avg_ppg', f'{year}_std_dev', f'{league.get("name")}_custom_pts', f'{league.get("name")}_custom_pts_vor']].to_csv(path.join(DATA_DIR, rf'vor\Fantasy_Pros_Projections_{date}_with_VOR_Condensed_{league.get("name")}.csv'), index=False)

    rows, cols = merged_df.shape
    print(f'All done! The dataframe has {rows} rows and {cols} columns.')
    error_list_len = len(errors_list)
    print(f'There were {error_list_len} errors.\n The error list is: {errors_list}.')
    print(merged_df.head())