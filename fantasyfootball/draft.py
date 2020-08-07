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
from fantasyfootball import fpkmeans
from fantasyfootball.config import FIGURE_DIR, DATA_DIR
from os import path
import fantasyfootball.ffcalculator as ffcalculator

league = config.justin
elbow = fpkmeans.total_elbow
pos_list = ['qb', 'wr', 'te', 'rb']
today = date.today()
date = today.strftime('%Y.%m.%d')
weekly_stats = pd.read_csv(path.join(DATA_DIR, r'game-by-game\2019_weekly.csv'))
errors_list = []
try:
    df_list = []
    for pos in pos_list:
        url = f'https://www.fantasypros.com/nfl/projections/{pos}.php?week=draft&scoring=PPR&week=draft'
        fp_df = fp.fantasy_pros_stats_process(url)
        fp_df['pos'] = pos.upper()
        fp_df['temp_name'] = fp_df['player_name']
        fp_df = config.char_replace(fp_df, 'temp_name')
        fp_df = config.unique_id_create(fp_df, 'temp_name', 'pos')
        #add custom scoring
        fp_df = config.fantasy_pros_pts(fp_df, league)
        df_list.append(fp_df)
    df = pd.concat(df_list)
    df.drop(columns=['temp_name'], inplace=True)
    df.sort_values(f'{league.get("name")}_custom_pts', ascending=False, inplace=True)

except Exception as e:
    # Store the url and the error it causes in a list
    error =[e]  
    # then append it to the list of errors
    errors_list.append(error)

adp_df = ffcalculator.adp_scrape(league)
adp_df = ffcalculator.adp_column_clean(adp_df, league)
adp_df = config.char_replace(adp_df, 'name')
adp_df = config.unique_id_create(adp_df, 'name', 'pos')

#combines DFs
merged_df = df.merge(adp_df, how='left', on='id').sort_values('adp').reset_index(drop=True)
merged_df.drop(columns=['name', 'pos_y', 'team'], inplace=True)
merged_df.rename(columns={'pos_x' : 'pos'}, inplace=True)
                
weekly_stats.columns = [col.lower() for col in weekly_stats.columns]

#cleans names so we can create a unique id across different sites
weekly_stats['temp_name'] = weekly_stats['player_name']
weekly_stats = config.char_replace(weekly_stats, 'temp_name')
weekly_stats = config.unique_id_create(weekly_stats, 'temp_name', 'pos')
weekly_stats.drop(columns=['temp_name'], inplace=True)
year = weekly_stats['year'].max()
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
merged_df[f'{league.get("name")}_custom_pts_vor'] = merged_df[f'{league.get("name")}_custom_pts'] - merged_df['pos'].map(replacement_value)
merged_df.sort_values(f'{league.get("name")}_custom_pts_vor', inplace=True, ascending=False)
merged_df.reset_index(drop=True)

#add tiers
ecr = fp.fantasy_pros_ecr_process(league)
ecr = ecr.merge(merged_df, how='left', on=['player_name', 'pos', 'tm']).reset_index(drop=True)
ecr.drop(columns=['adp_x', 'bye_y'], inplace=True)
ecr.rename(columns={'adp_y' : 'adp', 'bye_x': 'bye'}, inplace=True)
tier_df = fpkmeans.assign_k_means_total_cutoff_cluster(ecr, elbow)

#cleanup columns
tier_df.rename(columns={
    f'{league.get("name")}_custom_pts': 'custom_points',
    f'{league.get("name")}_custom_pts_vor': 'vor',
    f'{year}_avg_ppg': 'py_avg_ppg',
    f'{year}_std_dev': 'py_std_dev'
    }, inplace=True)
tier_df = tier_df[['rank', 'pos_tiers', 'player_name', 'tm', 'pos_rank', 'pos', 'bye', 'best', 'worst', 'avg', 'std dev', 'adp',
                    'py_avg_ppg', 'py_std_dev', 'custom_points', 'vor']]

#export to CSVs
tier_df.to_csv(path.join(DATA_DIR, rf'vor\{date}_{league.get("name")}_draft.csv'), index=False)

error_list_len = len(errors_list)
print(f'There were {error_list_len} errors.\n The error list is: {errors_list}.')
print(tier_df.head())