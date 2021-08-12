# draft.py

from sklearn.cluster import KMeans 
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from matplotlib import patches as mpatches
import numpy as np
from mpl_toolkits import mplot3d
from fantasyfootball import fantasypros as fp
import matplotlib.style as style
from datetime import date
from fantasyfootball import config
from fantasyfootball import tiers
from fantasyfootball.config import FIGURE_DIR, DATA_DIR
from os import path
from fantasyfootball import ffcalculator

pos_tier_dict_viz = {
    'RB' : 8,
    'QB' : 7,
    'WR' : 8,
    'TE' : 5,
    'DST' : 5,
    'K' : 4
    }

league = config.sean
weekly_stats_year = 2020
today = date.today()
date = today.strftime('%Y.%m.%d')
weekly_path = path.join(DATA_DIR, rf'game-by-game\{weekly_stats_year}_weekly.csv')
replacement_method = 'top n'

def get_fantasy_pros_projections(week='draft', league=league, make_id=True):
    """Grabs fantasy pros stat projections for a given league type
    make_id :: Boolean option to create a unique id in order to merge to other DFs"""
    return fp.fantasy_pros_pos_projection_scrape(week=week, league=league, make_id=make_id)

def get_adp_data(league=league):
    """Grabs ADP data from FF Calculator and adds a unique ID """
    return (ffcalculator.adp_process(league=league)
                        .pipe(config.unique_id_create))

def combine_fantasy_pros_and_adp_data():
    """Combines the FP stats DF and the ADP DF """
    fp = get_fantasy_pros_projections()
    adp = get_adp_data()
    return (fp.merge(adp, how='left', on='id')
               .sort_values('adp')
               .reset_index(drop=True)
               .drop(columns=['player_name_y', 'pos_y', 'team'])
               .rename(columns={'pos_x' : 'pos', 'player_name_x': 'player_name'}))

def transform_weekly_stats(df, league=league):
    """Transforms col names to lowercase, adds a unique ID and adds a column with custom fantasy points for a given league's rules """
    df = df.copy()
    df.columns = [col.lower() for col in df.columns]
    return df.pipe(config.unique_id_create).pipe(config.pro_football_reference_pts, league)

def aggregate_weekly_stats(df, league=league, year=weekly_stats_year):
    """Takes a weekly season long DF and adds avg points per game and standard deviation to measure consistency"""
    df = df.copy()
    return (df.groupby('id')
                      .agg(avg_ppg=(f'{league.get("name")}_custom_pts', 'mean'),
                           std_dev=(f'{league.get("name")}_custom_pts', 'std'))
                      .rename(columns={'avg_ppg' : f'{year}_avg_ppg', 'std_dev' : f'{year}_std_dev'})
         )
def get_weekly_data(file_path=weekly_path):
    """Puts together all weekly data functions in a single call """
    df = pd.read_csv(file_path)
    return df.pipe(transform_weekly_stats).pipe(aggregate_weekly_stats)

def merge_weekly_and_fantasy_pros_and_adp_data():
    """Combines weekly data, fantasy pros stat projections and ADP data in a single DF"""
    weekly = get_weekly_data()
    fp = combine_fantasy_pros_and_adp_data()
    return (fp.merge(weekly, how='left', on='id')
                      .reset_index(drop=True)
                      .drop(columns=['id']))

def map_replacement_value(league=league, method=replacement_method):
    """Calculates a position specific replacement value and maps he value to the merged DF
    Method :: 'avg starter' : replacement value for an avg starter
              'top n' : position specific cut-off
              'replacement player' : player who should be available on waivers
              'last starter' : value for a low-end starter
              """
    pos_list = ['qb', 'wr', 'te', 'rb']
    df = merge_weekly_and_fantasy_pros_and_adp_data()
    if method == 'avg starter':
        replacement_value = config.value_over_avg_starter(df, pos_list, league)
    elif method == 'top n':
        replacement_value = config.value_through_n_picks(df, pos_list, league)
    elif method == 'replacement player':
        replacement_value = config.value_over_replacement_player(df, pos_list, league)
    elif method == 'last starter':
        replacement_value = config.value_over_last_starter(df, pos_list, league)
    return df.assign(vor= df[f'{league.get("name")}_custom_pts'] - df['pos'].map(replacement_value))

def normalize_series(x):
    """Function used to normalize the VOR score using min-max normalization"""
    return (x - x.min()) / (x.max() - x.min())

def transform_ranking_and_vor():
    """Adds VOR differential, VOR rank and ADP rank; normalizes VOR score"""
    df = map_replacement_value()
    return (df.assign(vor_rank= lambda x: x['vor'].rank(ascending=False),
                              adp_rank= lambda x: x['overall'].rank(),
                              adp_vor_delta= lambda x: x['adp_rank'] - x['vor_rank'])
              .drop(columns=['vor_rank', 'adp_rank'])
              .assign(vor=lambda x: x['vor'].pipe(normalize_series))
              .sort_values('vor', ascending=False)
              .reset_index(drop=True))

def merge_ecr_data(league=league):
    """Takes the finalized VOR DF and combines with the ECR data scraped from Fantasy Pros """
    df = transform_ranking_and_vor()
    return (fp.fantasy_pros_ecr_process(league)
              .merge(df, how='left', on=['player_name', 'pos', 'tm'])
              .reset_index(drop=True)
              .drop(columns=['bye_y'])
              .rename(columns={'bye_x': 'bye'}))

def add_tiers_to_ecr(league=league):
    """Adds tiers to the ECR DF using Gaussian Mixture Model """
    df = merge_ecr_data()
    pos_dict = tiers.draftable_position_quantity(league)
    return tiers.assign_tier_to_df(df, tier_dict=pos_tier_dict_viz, kmeans=False, pos_n=pos_dict, covariance_type='diag')

def run_draft_script(save=True, year=weekly_stats_year):
    """Outputs final dataframe with ECR data with the additional tiers, weekly stats aggs, custom points and VOR columns """
    df = add_tiers_to_ecr()
    df = df.rename(columns={
    f'{league.get("name")}_custom_pts': 'custom_points',
    f'{year}_avg_ppg': 'py_avg_ppg',
    f'{year}_std_dev': 'py_std_dev'
    })
    df = df[['rank', 'pos_tiers', 'player_name', 'tm', 'pos_rank', 'pos', 'bye', 'best', 'worst', 'avg', 'std dev', 'adp',
                    'adp_vor_delta', 'py_avg_ppg', 'py_std_dev', 'custom_points', 'vor']]
    if save:
        df.to_csv(path.join(DATA_DIR, rf'vor\{date}_{league.get("name")}_draft.csv'), index=False)
    return df.head()

run_draft_script(save=True)