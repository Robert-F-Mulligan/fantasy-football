# pfrweeklyanalysis.py

import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from os import path
from fantasyfootball.config import DATA_DIR, pfr_to_fantpros, nfl_color_map, nfl_logo_espn_path_map
from pathlib import Path
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
import seaborn as sns
from fantasyfootball.tiersweekly import work_list, sean_list, justin_list, different_spelling

BASE_URL = "https://www.pro-football-reference.com/play-index/pgl_finder.cgi?request=1&match=game&year_min={season}&year_max={season}&season_start=1&season_end=-1&pos%5B%5D=QB&pos%5B%5D=WR&pos%5B%5D=RB&pos%5B%5D=TE&pos%5B%5D=OL&pos%5B%5D=DL&pos%5B%5D=LB&pos%5B%5D=DB&is_starter=E&game_type=R&game_num_min=0&game_num_max=99&week_num_min={week}&week_num_max={week}&c1stat=rush_att&c1comp=gt&c1val=0&c2stat=targets&c2comp=gt&c2val=0&c5val=1.0&order_by=rush_yds&offset={offset}"
season = 2020
OUTPUT_DIR = Path(path.join(DATA_DIR, 'weekly-analysis', f'{season}'))

FLOAT_COL = ['age', 'rushing_att', 'rushing_yds','rushing_y/a', 'rushing_td', 'receiving_tgt', 'receiving_rec', 'receiving_yds', 'receiving_y/r', 'receiving_td', 'receiving_y/tgt']

def pfr_get_weekly_stats(season, week):
    df = pfr_get_data(season, week)
    df = pfr_clean_data(df)
    return df

def pfr_get_data(season=2020, week=1):
    offset = 0
    df = pd.DataFrame()
    while True:
        URL = BASE_URL.format(season=season, week=week, offset=offset)
        res = requests.get(URL)
        soup = BeautifulSoup(res.content, 'html.parser')
        table = soup.find('table', {'id': 'results'})
        new_df = pd.read_html(str(table))[0]
        if new_df.shape[0] == 0: 
          break
        offset+=100 # increment the offset by 100 to flip to the next page
        df = pd.concat([df, new_df])
    return df

def pfr_clean_data(df):
    df = df.copy()
    pos_map= {'WR/RS': 'WR', 'RB/WR': 'RB', 'HB': 'RB'}
    df.columns = ['_'.join(col) for col in df.columns]
    df = df.rename(columns={
                'Unnamed: 7_level_0_Unnamed: 7_level_1': 'home/away',
                'Unnamed: 1_level_0_Player': 'player_name'})
    df.columns = [col.lower() for col in df.columns]            
    df.columns = [i.split('_')[-1] if 'level' in str(i) else i for i in df.columns]
    df = (df.loc[df['rk'] != 'Rk']
            .replace({'home/away': {'@' : 'Away', np.nan: 'Home'}})
            .replace({'pos': pos_map})
            .reset_index(drop=True)
            .drop(columns=['receiving_ctch%'])
    )
    df[FLOAT_COL] = df[FLOAT_COL].astype('float')
    return df

def pfr_transform_df(df):
    df = (df.copy()
            .rename(columns={'receiving_tgt': 'tgt_ind', 'rushing_att': 'att_ind'})
            .replace({'tm': pfr_to_fantpros})
         )
    df['att_tm'] = df.loc[df['pos'] == 'RB'].groupby('tm')['att_ind'].transform('sum')
    df['tgt_tm'] = df.groupby('tm')['tgt_ind'].transform('sum')
    df['rushing_share'] = df['att_ind'] / df['att_tm']
    df['tgt_share'] = df['tgt_ind'] / df['tgt_tm']
    return df

def make_rb_tgt_share_viz(df, pos='RB', x_size=20, y_size=15, save=True, player_list=None):
    df = df.loc[(df['pos'] == pos) & (df['tgt_share'] > 0) & (df['rushing_share'] > 0)]
    week = df['week'].max()
    season = df['date'][0][:4]
    sns.set_style('whitegrid');
    fig, ax = plt.subplots(figsize=(x_size,y_size))
    ax.set_yticks(np.linspace(0, df['tgt_share'].max(), 15))
    ax.set_xticks(np.linspace(0, df['rushing_share'].max(), 15));
    ax.set_xlabel('Rushing Share', fontsize=12)
    ax.set_ylabel('Target Share', fontsize=12)
    ax.set_title(f'{pos} rushing share vs. target share for {season} week {week}', fontsize=16, fontweight='bold')

    for _, row in df.iterrows():
        player = row['player_name']
        if player in player_list:
            ax.scatter(row['rushing_share'], row['tgt_share'], color='red', alpha=1.0, zorder=2)
            ax.annotate(row['player_name'], xy=(row['rushing_share']+.01, row['tgt_share']), alpha=1.0, zorder=2)
        else:
            ax.scatter(row['rushing_share'], row['tgt_share'], color='blue', alpha=0.5, zorder=1)
            ax.annotate(row['player_name'], xy=(row['rushing_share']+.01, row['tgt_share']), alpha=0.5, zorder=1)
    if save:
        fig.savefig(path.join(OUTPUT_DIR, f'{season}_week_{week}_{pos}_target_share_rushing_share.png'))

def make_target_share_barh_viz(df, top_n=25, x_size=20, y_size=20):
    df= df.copy()
    week = df['week'].max()
    pos_list = ['RB', 'TE', 'WR']
    df = df.loc[df['pos'].isin(pos_list)]
    df = df.sort_values('tgt_share',ascending=False).head(top_n).reset_index().copy()
    
    sns.set_style('whitegrid');
    fig,ax = plt.subplots(figsize=(x_size, y_size))
    ax.set_xlabel('% of Team Targets', fontsize=20)
    ax.set_ylabel('Top 25 Team Target Share', fontsize=20)
    ax.invert_yaxis()
    ax.margins(x=.05, y=0)
    ax.yaxis.grid(False)
    ax.set_title(f'Top 25 Team Target Share - Week {week}', fontsize=20, fontweight='bold')
    ax.annotate('Data: Pro Football Reference',xy=(.85,-0.05), fontsize=12, xycoords='axes fraction')

    for ix, row in df.iterrows():
        player = row['player_name']
        team = row['tm']
        
        ax.barh(player, row['tgt_share'],  color=nfl_color_map[team])
        ax.annotate('{:.3f}'.format(row['tgt_share']), xy=(row['tgt_share']+0.001, player))
        
        file_path = nfl_logo_espn_path_map[team]
        img = plt.imread(file_path)
        xy = (0.01, ix)
        im = OffsetImage(img, zoom=.1)
        ab = AnnotationBbox(im, xy, frameon=False, xycoords='data')                                 
        ax.add_artist(ab)

if __name__ == "__main__":
    season = 2020
    week = int(input('Week? >>> '))

    df = pfr_get_weekly_stats(season, week)

    output_file = f'{season}_week_{week}.csv'
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(path.join(OUTPUT_DIR, output_file), index=False)

    #generate rb tgt share
    player_list = work_list + sean_list + justin_list + different_spelling
    df = pfr_transform_df(df)
    make_rb_tgt_share_viz(df,  player_list=player_list)
