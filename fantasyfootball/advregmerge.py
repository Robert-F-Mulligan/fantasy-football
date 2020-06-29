#advregmerge.py

import pandas as pd
from os import path
import fantasyfootball.config

league = config.sean

DATA_DIR = r'../Data/processed'

df_source = r'../raw/Game by Game Breakdown_2018_2019.csv'
adv_source =  r'../raw/Advanced Stats Game by Game Breakdown_2018_2019.csv'

df = pd.read_csv(path.join(DATA_DIR,df_source))
df_adv = pd.read_csv(path.join(DATA_DIR,adv_source))

new_df = df.merge(df_adv, on=['player_id', 'date'])

new_df.drop(columns=['player_name_y', 'pos_y', 'year_y'], inplace=True)
new_df.rename(columns={
    'player_name_x' : 'player_name',
    'pos_x' : 'pos',
    'year_x': 'year'
}, inplace=True)

#scoring columns
new_df['std_scoring'] = (0.1*(new_df['rushing_yds'] + new_df['receiving_yds']) + 0.04*new_df['passing_yds']
                         + -3*(new_df['fumbles'] + new_df['passing_int']) +
                         6*(new_df['passing_td'] + new_df['rushing_td'] + new_df['receiving_td']))

new_df['ppr_scoring'] = new_df['std_scoring'] + 1*new_df['receiving_rec']
new_df['half_ppr_scoring'] = new_df['std_scoring'] + 0.5*new_df['receiving_rec']  
pro_football_reference_pts(new_df, league)

min_year = new_df['year'].min()
max_year = new_df['year'].max()

new_df.to_csv(path.join(DATA_DIR,f'Merged_Advanced_Stats_{min_year}_{max_year}.csv'), index=False)

print('All done!')