# nflfastrfuncs.py

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
import fantasyfootball
from os import path
from fantasyfootball.config import DATA_DIR, pfr_to_fantpros, nfl_color_map, nfl_logo_espn_path_map
import seaborn as sns
import numpy as np
from fantasyfootball.config import FIGURE_DIR

def get_nfl_fast_r_data(*years):
    df_list = []
    for year in years:
        year_df = pd.read_csv('https://github.com/guga31bb/nflfastR-data/blob/master/data/' \
                            'play_by_play_' + str(year) + '.csv.gz?raw=True',
                            compression='gzip', low_memory=False)
        df_list.append(year_df)
    df = pd.concat(df_list)
    return df

def get_nfl_fast_r_roster_data():
    df = pd.read_csv('https://github.com/guga31bb/nflfastR-data/blob/master/roster-data/' \
                            'roster.csv.gz?raw=true', compression='gzip', low_memory=False)
    return df

def target_share_vs_air_yard_share(df):
    year = df['game_id'].str.split('_').str[0].max()
    week = df['week'].max()
    my_cols = ['receiver', 'posteam', 'play_type', 'air_yards']
    play_type = df['play_type'] == 'pass'
    df =  df.loc[play_type, my_cols].copy()
    df = (df.groupby(['receiver', 'posteam'])
            .agg(targets=('play_type', 'count'), air_yards=('air_yards', 'sum'))
            .sort_values('targets', ascending=False)
            .reset_index()
            .replace({'posteam' : {'LA': 'LAR'}})
             )
    df = (df.assign(team_targets=df.groupby('posteam')['targets'].transform('sum'))
           .assign(team_air_yards=df.groupby('posteam')['air_yards'].transform('sum'))
         )
    df = (df.assign(target_share=df['targets'] / df['team_targets'])
            .assign(air_yard_share= df['air_yards'] / df['team_air_yards'])
            .assign(year=year)
            .assign(week=week)
         )
    return df

def target_share_vs_air_yard_share_viz(df, *team_filter, n=60, x_size=20, y_size=15, save=True):
    if len(team_filter) > 0:
        team_list = []
        for team in team_filter:
            team_list.append(team)
        df = df.loc[df['posteam'].isin(team_list)].copy()
    else:
        df = df.head(n).copy()
    sns.set_style('whitegrid');
    df['color'] = df['posteam'].map(nfl_color_map)
    fig, ax = plt.subplots(figsize=(x_size, y_size))
    ax.scatter(df['target_share'], df['air_yard_share'], color=df['color'], alpha=1.0)
    text = [ax.annotate(name, xy=(x+.001, y), alpha=1.0, zorder=2) for name, x, y 
        in zip(df['receiver'], df['target_share'], df['air_yard_share'])]
    #axis formatting
    ax.set_xlabel('Target Share', fontsize=12)
    ax.set_ylabel('Air Yard Share', fontsize=12)
    ax.set_xticks(np.linspace(0, df['target_share'].max(), 10))
    xlabels = ["{:.2%}".format(x) for x in np.linspace(0, df['target_share'].max(), 10)]
    ax.set_xticklabels(xlabels)
    ax.set_yticks(np.linspace(0, df['air_yard_share'].max(), 10))
    ylabels = ["{:.2%}".format(x) for x in np.linspace(0, df['air_yard_share'].max(), 10)]
    ax.set_yticklabels(ylabels)
    #mean lines
    avg_target_share = df['target_share'].mean()
    avg_air_yard = df['air_yard_share'].mean()  
    ax.axvline(avg_target_share, linestyle='--', color='gray')
    ax.axhline(avg_air_yard, linestyle='--', color='gray')
    #title
    year = df['year'].max()
    week = df['week'].max()
    ax.set_title(f'{year} Target Share vs Air Yard Share (Through Week {week})', fontsize=16, fontweight='bold')
    #margins and footnotes
    ax.margins(x=.05, y=.01)
    ax.annotate('Data: @NFLfastR',xy=(.90,-0.05), fontsize=12, xycoords='axes fraction')
    ax.annotate('Figure: @MulliganRob',xy=(.90,-0.07), fontsize=12, xycoords='axes fraction');
    if save:
        fig.savefig(path.join(FIGURE_DIR, f'{year}_through_week_{week}_Target_Share_vs_Air_Yard_Share.png'))
    return plt.show()

def carries_inside_5_yardline_transform(df):
    df = df.copy()
    year = df['game_id'].str.split('_').str[0].max()
    week = df['week'].max()
    inside_5 = df.loc[(df['yardline_100']<5) &
             (df['play_type']=='run')]
    carries_5 = (
    inside_5.groupby(['rusher','posteam'])[['play_id']]
    .count()
    .reset_index()
    .sort_values(by=['play_id'],ascending=False)
    .reset_index(drop=True)
    )
    carries_5 = (carries_5.assign(year=year)
                          .assign(week=week)
    )
    return carries_5

def carries_inside_5_yardline_viz(df, *team_filter, n=20, x_size=20, y_size=15, save=True):
    if len(team_filter) > 0:
        team_list = []
        for team in team_filter:
            team_list.append(team)
        df = df.loc[df['posteam'].isin(team_list)].copy()
    else:
        df = df.head(n).copy()
    #color and logo mapping
    df['color'] = df['posteam'].map(nfl_color_map)
    df['logo'] = df['posteam'].map(nfl_logo_espn_path_map)
    sns.set_style('whitegrid');
    fig,ax = plt.subplots(figsize=(x_size, y_size))
    ax.barh(df['rusher'], df['play_id'], color=df['color'])
    text = [ax.annotate(carries, xy=(x, y), fontsize=12) for carries, x, y in 
            zip(df['play_id'], df['play_id'], df['rusher'])]
    images = [OffsetImage(plt.imread(file_path), zoom=.1) for file_path in df['logo'].to_list()]
    x0 = [(df['play_id'].max() * 0.02)] * len(df['play_id'])
    logos = [ax.add_artist(AnnotationBbox(im, xy=(x,y), frameon=False, xycoords='data')) 
             for im, x, y in zip(images, x0, df['rusher'])]
    #axis formatting
    ax.invert_yaxis()
    ax.margins(x=.05, y=0)
    ax.yaxis.grid(False)
    #title
    year = df['year'].max()
    week = df['week'].max()
    ax.set_title(f'{year} Carries Inside the 5 Yardline (Through Week {week})', fontsize=16, fontweight='bold')
    #margins and footnotes
    ax.margins(x=.05, y=.01)
    ax.annotate('Data: @NFLfastR',xy=(.90,-0.05), fontsize=12, xycoords='axes fraction')
    ax.annotate('Figure: @MulliganRob',xy=(.90,-0.07), fontsize=12, xycoords='axes fraction');
    if save:
        fig.savefig(path.join(FIGURE_DIR, f'{year}_through_week_{week}_Carries_Inside_5_Yardline.png'))
    return plt.show()