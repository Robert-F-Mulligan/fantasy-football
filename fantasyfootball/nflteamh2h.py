# nflteamh2h.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from bs4 import BeautifulSoup
import requests
from fantasyfootball.config import fftoday_team_map, nfl_color_map, nfl_wordmark_path_map, FIGURE_DIR
from fantasyfootball import nflfastr
from os import path

def fftoday_fantasy_points_scored_scrape(pos, season=2020, side='Scored', league='Yahoo'):
    """
    Offense = 'Scored'
    Defense = 'Allowed'
    """
    pos = pos.upper()
    pos_dict = {'QB': 10, 'RB':20, 'WR':30, 'TE':40}
    league_dict = {'ESPN': 26955, 'Yahoo': '17'}
    league_var = league_dict[league]
    pos_var = pos_dict[pos]
    url = rf'https://fftoday.com/stats/fantasystats.php?Season={season}&GameWeek=Season&PosID={pos_var}&Side={side}&LeagueID={league_var}'
    r = requests.get(url)
    soup = BeautifulSoup(r.content,'html.parser')
    table = soup.find_all('table')
    return pd.read_html(str(table))[6]

def fftoday_fantasy_points_scored_transform(df):
    df = df.copy()
    header_row = 1
    df.columns = df.iloc[header_row]
    df.columns = [col.lower() for col in df.columns]
    df = df.drop(header_row).iloc[header_row:].reset_index(drop=True)
    df['team'] = df['team'].str.split().str[1].replace(fftoday_team_map)
    df = (df.set_index('team')
            .apply(pd.to_numeric))
    return df

def fftoday_fantasy_points_scored_by_pos(year=2020, side='Scored', rank=True):
    pos_list = ['QB', 'RB', 'WR', 'TE']
    df_list = []
    for pos in pos_list:
        df = (fftoday_fantasy_points_scored_scrape(pos, year, side)
              .pipe(fftoday_fantasy_points_scored_transform))
        df = df['fpts/g'].rename(f'{pos.lower()}_fpts/g')
        df_list.append(df)
    df = pd.concat(df_list, axis='columns')
    if rank and side=='Scored':
        df = df.rank(ascending=False, method='min')
    elif rank and side=='Allowed':
        df = df.rank(method='min')
    return df

def fftoday_fantasy_points_o_vs_by_pos(year=2020, rank=True):
    off = fftoday_fantasy_points_scored_by_pos(year=year, side='Scored', rank=rank)
    off['unit'] = 'offense'
    
    def_ = fftoday_fantasy_points_scored_by_pos(year=year, side='Allowed', rank=rank)
    def_['unit'] = 'defense'
    
    return pd.concat([off, def_]).set_index('unit', append=True)

def combine_off_vs_def_sources(year, rank=True):
    """Combines NFLfastr stats with FF Today stats"""
    #nflfastr
    fastrdf = nflfastr.get_nfl_fast_r_data(year)
    year = fastrdf['game_id'].str.split('_').str[0].max()
    week = fastrdf['week'].max()
    fastr_c = nflfastr.offense_vs_defense_transform(fastrdf, rank=rank)
    #fftoday
    fftoday_df = fftoday_fantasy_points_o_vs_by_pos(year, rank)
    #combining data
    data_list = [fastr_c, fftoday_df]
    return pd.concat(data_list, axis='columns').assign(year=year).assign(week=week)

def make_unit_compare_bar(df, *teams, unit='offense', width=0.75, legend='best', save=False):
    year = df['year'].max()
    week = df['week'].max()
    df = df.copy().drop(columns=['year', 'week'])
    if teams:
        team_list = [(team, unit) for team in teams]
        df = df.loc[team_list].reindex(team_list).droplevel(1)
    df = df.T
    rank = np.arange(1,33) #create an array for all ranking possibilities
    rank_inv = rank[::-1] #create a reversed list
    rank_map = dict(zip(rank, rank_inv))
    rank_inv_map = dict(zip(rank_inv, rank)) #for labeling the bars

    #invert bar rankings, lower rank means taller bar
    df = df.replace(rank_map)
    
    colors = [nfl_color_map[team] for team in df.columns]
    #colors[1] = '#000000' override color if red and green
    fig, ax = plt.subplots(figsize=(30,15))
    df.plot(kind='bar', ax=ax, color=colors, width=width)

    #axis
    xlabels = ['Pass Eff.', 'Rush Eff.', 'Off. Sack Rate', 'Def. Sack Rate', 'Neutral Pace', 'QB FPPG', 'RB FPPG', 'WR FPPG', 'TE FPPG']
    ax.set_ylabel('Ranking',fontsize=20,labelpad=15)
    ax.set_ylim(0,33)
    ax.set_yticklabels([])
    ax.set_xticklabels(xlabels, rotation=0, ha='center', fontsize=20)
    ax.tick_params(
        which='both',
        bottom=False,
        left=False,
        right=False,
        top=False)
    
    #add grid
    ax.grid(zorder=0,alpha=.4)
    ax.set_axisbelow(True)
    
    #legend
    label_list = [team + ' ' + unit[0].upper() for team in df.columns]
    ax.legend(labels=label_list, fontsize=20, loc=legend)
    
    #annotate thr bar charts
    for p in ax.patches:
        converted_height = rank_inv_map[p.get_height()]
        ax.annotate(format(converted_height, '.0f'), 
                       (p.get_x() + p.get_width() / 2., p.get_height()), 
                       ha = 'center', va = 'center', 
                       size=15,
                       xytext = (0, 10), 
                       textcoords = 'offset points')
    
    #team wordmarks
    if len(teams) == 2:
        logo_path = [nfl_wordmark_path_map[team] for team in df.columns]
        images = [OffsetImage(plt.imread(file_path), zoom=1.1) for file_path in logo_path]
        coordinates = [(.25, 1.03), (.75, 1.03)]
        for co, im in zip(coordinates, images):
            ax.add_artist(AnnotationBbox(im, xy=co, frameon=False, xycoords='axes fraction'))

    #title and footnote
    fig.suptitle(f'{year} Week {week} Matchup', fontsize=30, fontweight='bold', y=0.92)
    ax.annotate('Data: NFLfastR, FF Today\nFigure: @MulliganRob',xy=(.9,-0.07), fontsize=12, xycoords='axes fraction')
    
    if save:
        teams_str = '_'.join(teams)
        fig.savefig(path.join(FIGURE_DIR, f'{year}_through_week_{week}_h2h_{teams_str}.png'))

def make_o_vs_d_compare_bar(df, offense, defense, width=0.75, legend='best', save=False):
    """
    Compare two NFL teams offense vs defense
    """
    year = df['year'].max()
    week = df['week'].max()
    df = (df.copy()
            .loc[[(offense, 'offense'), (defense, 'defense')]]
            .drop(columns=['year', 'week'])
            .droplevel(1)
            .reindex([offense, defense]))
    team_list = [team for team in df.index]
    df = df.T
    rank = np.arange(1,33) #create an array for all ranking possibilities
    rank_inv = rank[::-1] #create a reversed list
    rank_map = dict(zip(rank, rank_inv))
    rank_inv_map = dict(zip(rank_inv, rank)) #for labeling the bars
    
    #invert bar rankings, lower rank means taller bar
    df = df.replace(rank_map)
    
    colors = [nfl_color_map[team] for team in df.columns]
    #colors[1] = '#000000' #override color if red and green
    fig, ax = plt.subplots(figsize=(30,15))
    df.plot(kind='bar', ax=ax, color=colors, width=width)

    #axis
    xlabels = ['Pass Eff.', 'Rush Eff.', 'Sack Rate', 'Neutral Pace', 'QB FPPG', 'RB FPPG', 'WR FPPG', 'TE FPPG']
    ax.set_ylabel('Ranking',fontsize=20,labelpad=15)
    ax.set_ylim(0,33)
    ax.set_yticklabels([])
    ax.set_xticklabels(xlabels, rotation=0, ha='center', fontsize=20)
    
    ax.tick_params(
        which='both',
        bottom=False,
        left=False,
        right=False,
        top=False)
    
    #add grid
    ax.grid(zorder=0,alpha=.4)
    ax.set_axisbelow(True)
    
    #legend
    ax.legend(labels=[offense + ' O' , defense + ' D'], fontsize=20, loc=legend)
    
    #annotate thr bar charts
    for p in ax.patches:
        converted_height = rank_inv_map[p.get_height()]
        ax.annotate(format(converted_height, '.0f'), 
                       (p.get_x() + p.get_width() / 2., p.get_height()), 
                       ha = 'center', va = 'center', 
                       size=15,
                       xytext = (0, 10), 
                       textcoords = 'offset points')
    
    #team wordmarks
    logo_path = [nfl_wordmark_path_map[team] for team in df.columns]
    images = [OffsetImage(plt.imread(file_path), zoom=1.1) for file_path in logo_path]
    coordinates = [(.25, 1.03), (.75, 1.03)]
    for co, im in zip(coordinates, images):
        ax.add_artist(AnnotationBbox(im, xy=co, frameon=False, xycoords='axes fraction'))

    #title and footnote
    fig.suptitle(f'{year} Week {week} Matchup', fontsize=30, fontweight='bold', y=0.92)
    ax.annotate('Data: NFLfastR, FF Today\nFigure: @MulliganRob',xy=(.9,-0.07), fontsize=12, xycoords='axes fraction')
    
    if save:
        teams_str = '_'.join(team_list)
        fig.savefig(path.join(FIGURE_DIR, f'{year}_week_{week}_Off_vs_Def_{teams_str}.png'))