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

league = config.justin
pos_list = ['qb', 'wr', 'te', 'rb']
today = date.today()
date = today.strftime('%Y.%m.%d')
weekly_stats = pd.read_csv(path.join(DATA_DIR, r'game-by-game\2019_weekly.csv'))
errors_list = []
try:
    df = fp.fantasy_pros_pos_projection_scrape(week='draft', league=league, make_id=True)

except Exception as e:
    # Store the url and the error it causes in a list
    error =[e]  
    # then append it to the list of errors
    errors_list.append(error)

adp_df = ffcalculator.adp_process(league=league)
adp_df = config.unique_id_create(adp_df)

#combines DFs
merged_df = (df.merge(adp_df, how='left', on='id').sort_values('adp').reset_index(drop=True)
               .drop(columns=['player_name_y', 'pos_y', 'team'])
               .rename(columns={'pos_x' : 'pos', 'player_name_x': 'player_name'})
            )
                
weekly_stats.columns = [col.lower() for col in weekly_stats.columns]

#cleans names so we can create a unique id across different sites
weekly_stats = config.unique_id_create(weekly_stats)
year = weekly_stats['year'].max()
weekly_stats = config.pro_football_reference_pts(weekly_stats, league)
agg_df = (weekly_stats.groupby('id')
                      .agg(avg_ppg =(f'{league.get("name")}_custom_pts', 'mean'),
                                        std_dev=(f'{league.get("name")}_custom_pts', 'std'))
                      .rename(columns={'avg_ppg' : f'{year}_avg_ppg', 'std_dev' : f'{year}_std_dev'})
         )

merged_df = (merged_df.merge(agg_df, how='left', on='id').reset_index(drop=True)
                      .drop(columns=['id'])
            )

#run the desired VBD function to calculate replacement player
replacement_value = config.value_through_n_picks(merged_df, league, pos_list)

#map replacement value to df and calculate value above replacement
merged_df[f'{league.get("name")}_custom_pts_vor'] = merged_df[f'{league.get("name")}_custom_pts'] - merged_df['pos'].map(replacement_value)
merged_df = (merged_df.sort_values(f'{league.get("name")}_custom_pts_vor', ascending=False)
                     .reset_index(drop=True)
            )

#add tiers
ecr = fp.fantasy_pros_ecr_process(league)
ecr = (ecr.merge(merged_df, how='left', on=['player_name', 'pos', 'tm']).reset_index(drop=True)
          .drop(columns=['adp_x', 'bye_y'])
          .rename(columns={'adp_y' : 'adp', 'bye_x': 'bye'})
      )

pos_dict = tiers.draftable_position_quantity(league)
#run elbow or AIC/BIC to determine optimal number of tiers
tier_df = tiers.assign_tier_to_df(ecr, tier_dict=pos_tier_dict_viz, kmeans=False, pos_n=pos_dict, covariance_type='diag')

#cleanup columns
tier_df = tier_df.rename(columns={
    f'{league.get("name")}_custom_pts': 'custom_points',
    f'{league.get("name")}_custom_pts_vor': 'vor',
    f'{year}_avg_ppg': 'py_avg_ppg',
    f'{year}_std_dev': 'py_std_dev'
    })
tier_df = tier_df[['rank', 'pos_tiers', 'player_name', 'tm', 'pos_rank', 'pos', 'bye', 'best', 'worst', 'avg', 'std dev', 'adp',
                    'py_avg_ppg', 'py_std_dev', 'custom_points', 'vor']]

#export to CSVs
tier_df.to_csv(path.join(DATA_DIR, rf'vor\{date}_{league.get("name")}_draft.csv'), index=False)

error_list_len = len(errors_list)
print(f'There were {error_list_len} errors.\n The error list is: {errors_list}.')
print(tier_df.head())