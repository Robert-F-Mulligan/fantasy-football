# nflfastr.py

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib import cm
import fantasyfootball
from os import path
from fantasyfootball.config import DATA_DIR, FIGURE_DIR, pfr_to_fantpros, nfl_color_map, nfl_color_map_secondary, nfl_logo_espn_path_map, nfl_wordmark_path_map
import seaborn as sns
import numpy as np
from adjustText import adjust_text
import requests
from io import BytesIO
import codecs
import urllib.request
from datetime import datetime
from IPython.display import HTML
import dataframe_image as dfi

def get_nfl_schedule_data(*years, current_week=False):
    """Retrives NFL schedule information from the NFLfastr git repo for a given year(s) 
    :current_week: will return the upcoming week schedule
    """
    df = pd.read_csv('https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
                     ,low_memory=False, parse_dates=['gameday'])
    if current_week:
        today = datetime.today()
        week_num = df.loc[df['gameday'] > today,'week'].min()
        df = df.loc[df['week']==week_num]
    elif years:
        year_list = [int(year) for year in years]
        df = df.loc[df['season'].isin(year_list)]
    return df

def get_current_season_year():
    """Returns the current/most recent NFL season year"""
    return get_nfl_schedule_data()['season'].max()

def get_nfl_fast_r_data(*years, regular_season=True, two_pt=False):
    """
    Retrives play by play data from the NFLfastr git repo for a given year(s) 
    :years: Specify an NFL season or seasons; default will be most recent season / current season
    """
    if not years or years[0] is None:
        years = [get_current_season_year()]
    df_list = [pd.read_csv('https://github.com/nflverse/nflverse-data/releases/download/' \
                            f'pbp/play_by_play_{year}.csv.gz',
                            compression='gzip', low_memory=False)
              for year in years]
    df = pd.concat(df_list)
    if regular_season:
        df = df.loc[df['season_type'] == 'REG']
    return df if two_pt else df.loc[df['down']<=4]

def get_nfl_fast_r_roster(*years):
    """Retrives roster data from the NFLfastr git repo for a given year(s) """
    df = pd.read_csv('https://github.com/nflverse/nflfastR-roster/blob/master/' \
                           'data/nflfastR-roster.csv.gz?raw=True', compression='gzip', low_memory=False)
    if years:
        year_list = [int(year) for year in years]
    df = df.loc[df['season'].isin(year_list)]
    return df

def get_team_colors_and_logos_dataframe():
    return pd.read_csv(r'https://raw.githubusercontent.com/nflverse/nflfastR-data/master/teams_colors_logos.csv')

def get_nfl_draft_data(*years):
    """Retrives team draft results from the NFLfastr git repo for a given year(s) """
    df = pd.read_csv('https://raw.githubusercontent.com/nflverse/nfldata/master/data/draft_picks.csv',low_memory=False)
    if years:
        year_list = [int(year) for year in years]
    df = df.loc[df['season'].isin(year_list)]
    return df

def convert_to_gsis_id(new_id):
    """Apply this function to nflfastr play-by-play in order to join to 2020 roster data gsis_id """
    if type(new_id) == float:
        return new_id  
    return codecs.decode(new_id[4:-8].replace('-',''),"hex").decode('utf-8')

def get_year_and_week(df):
    """Extracts season and max week in an NFLfastr df; useful for labeling figures """
    year = int(df['game_id'].max().split('_')[0])
    week = df['week'].max()
    return year, week

def save_team_images(column='team_wordmark'):
    """Function will loop through a dataframe column and save URL images locally"""
    df = pd.read_csv(r'https://raw.githubusercontent.com/nflverse/nflfastR-data/master/teams_colors_logos.csv')
    my_series = df[column]
    my_list = my_series.to_list()
    for im_url in my_list:
        image_url = im_url
        filename = image_url.split("/")[-1]
        local_path = r'..\figures'
        file_path = path.join(local_path, filename)
        urllib.request.urlretrieve(image_url, file_path)

def target_share_vs_ay_share_transform(df):
    """Calculates the team target share and total air yards for a given receiver """
    df = df.copy()
    year, week = get_year_and_week(df)
    play_type = df['play_type'] == 'pass'
    df =  (df.loc[play_type].copy()
            .groupby(['receiver_id', 'receiver'])
            .agg(posteam=('posteam', 'last'), targets=('play_type', 'count'), air_yards=('air_yards', 'sum'))
            .sort_values('targets', ascending=False)
            .assign(team_targets= lambda x: x.groupby('posteam')['targets'].transform('sum'))
            .assign(team_air_yards=lambda x: x.groupby('posteam')['air_yards'].transform('sum'))
            .assign(target_share=lambda x: x['targets'] / x['team_targets'])
            .assign(ay_share=lambda x: x['air_yards'] / x['team_air_yards'])
            .assign(year=year)
            .assign(week=week)
            .droplevel(0))
    return df

def target_share_vs_ay_share_viz(df, *team_filter, n=60, x_size=20, y_size=15, save=True):
    if team_filter:
        team_list = [team for team in team_filter]
        df = df.loc[df['posteam'].isin(team_list)].copy()
    else:
        df = df.head(n).copy()
    sns.set_style('whitegrid');
    df['color'] = df['posteam'].map(nfl_color_map)
    fig, ax = plt.subplots(figsize=(x_size, y_size))
    ax.scatter(df['target_share'], df['ay_share'], color=df['color'], s=300, alpha=0.7)
    text = [ax.annotate(name, xy=(x+.001, y), alpha=1.0, zorder=2, fontsize=12) for name, x, y 
        in zip(df.index, df['target_share'], df['ay_share'])]
    adjust_text(text)
    #axis formatting
    ax.tick_params(labelsize=14)
    ax.set_xlabel('Target Share', fontsize=16)
    ax.set_ylabel('Air Yard Share', fontsize=16)
    ax.set_xticks(np.linspace(0, df['target_share'].max(), 10))
    xlabels = ["{:.2%}".format(x) for x in np.linspace(0, df['target_share'].max(), 10)]
    ax.set_xticklabels(xlabels)
    ax.set_yticks(np.linspace(0, df['ay_share'].max(), 10))
    ylabels = ["{:.2%}".format(x) for x in np.linspace(0, df['ay_share'].max(), 10)]
    ax.set_yticklabels(ylabels)
    #mean lines
    avg_target_share = df['target_share'].mean()
    avg_air_yard = df['ay_share'].mean()  
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
        fig.savefig(path.join(FIGURE_DIR, f'{year}_through_week_{week}_Target_Share_vs_ay_share.png'))
    return plt.show()

def carries_inside_5_yardline_transform(df):
    """Calculates total carries a rusher has inside the 5 yardline """
    df = df.copy()
    year, week = get_year_and_week(df)
    play_type = df['play_type']=='run'
    inside_5 = df['yardline_100']<5
    df = (df.loc[play_type & inside_5]
            .groupby(['rusher_id', 'rusher'])
            .agg(posteam=('posteam', 'last'), play_count=('play_id', 'count'))
            .sort_values(by=['play_count'],ascending=False)
            .droplevel(0)
            .assign(year=year)
            .assign(week=week))
    return df

def carries_inside_5_yardline_viz(df, *team_filter, n=20, x_size=20, y_size=15, save=True):
    if team_filter:
        team_list = [team for team in team_filter]
        df = df.loc[df['posteam'].isin(team_list)].copy()
    else:
        df = df.head(n).copy()
    #color and logo mapping
    df['color'] = df['posteam'].map(nfl_color_map)
    df['logo'] = df['posteam'].map(nfl_logo_espn_path_map)
    sns.set_style('whitegrid');
    fig,ax = plt.subplots(figsize=(x_size, y_size))
    ax.barh(df.index, df['play_count'], color=df['color'])
    for carries, x, y in zip(df['play_count'], df['play_count'], df.index):
        ax.annotate(carries, xy=(x+0.02, y), fontsize=14)
    images = [OffsetImage(plt.imread(file_path), zoom=.1) for file_path in df['logo'].to_list()]
    x0 = [(df['play_count'].max() * 0.02)] * len(df['play_count'])
    for im, x, y in zip(images, x0, df.index):
        ax.add_artist(AnnotationBbox(im, xy=(x,y), frameon=False, xycoords='data'))
    #axis formatting
    ax.invert_yaxis()
    ax.margins(x=.05, y=0)
    ax.tick_params(axis='y', labelsize=14)
    ax.tick_params(axis='x', labelsize=14)
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

def air_yard_density_transform(df):
    """
    Transforms per a play airyard dataset into a format ready for a density plot 
    DF is sorted by descending total airyards
    """
    df = df.copy()
    year, week = get_year_and_week(df)
    play_type = df['play_type'] == 'pass'
    air_yard_threshold = ~df['air_yards'].isna()
    df = (df.loc[play_type & air_yard_threshold]
            .groupby(['receiver_id', 'receiver','play_id'])
            .agg(posteam=('posteam', 'last'), air_yards=('air_yards','sum'))
            .assign(total_air_yards= lambda x: x.groupby(['receiver_id'])['air_yards'].transform('sum'))
            .sort_values(['total_air_yards', 'receiver_id'], ascending=False)
            .drop(columns='total_air_yards')
            .droplevel([0,2])
            .reset_index()
            .assign(colors= lambda x: x['posteam'].map(nfl_color_map))
            .assign(logo= lambda x: x['posteam'].map(nfl_logo_espn_path_map))
            .assign(year=year)
            .assign(week=week))
    return df

def air_yard_density_viz(df, *team_filter, x_size=30, y_size=35, team_logo=True, save=True):
    if team_filter:
        team_list = [team for team in team_filter]
        df = df.loc[df['posteam'].isin(team_list)].copy()
        fig, axs = plt.subplots(2, 6, sharey=True, figsize=(x_size,y_size))
    else:
        df = df.copy()
        fig, axs = plt.subplots(5, 6, sharey=True, figsize=(x_size,y_size))

    ay_max = 40
    ay_min = -10

    axs_list = [item for sublist in axs for item in sublist] 
    axs_list_count = len(axs_list)

    ordered_groups = (df.groupby(['receiver', 'posteam']).sum()
                        .sort_values('air_yards', ascending=False).iloc[:axs_list_count].index
                    )
    grouped = df.groupby(['receiver', 'posteam'])
    for group_name in ordered_groups:
        ax = axs_list.pop(0)
        selection = grouped.get_group(group_name)
        player = group_name[0]
        team_color = selection['colors'].max()
        sns.kdeplot(selection['air_yards'], ax=ax, color=team_color, linewidth=3.0)

        #shading
        line = ax.lines[0]
        x = line.get_xydata()[:,0]
        y = line.get_xydata()[:,1]
        ax.fill_between(x, y, color=team_color, alpha=0.5)

        #formatting
        ax.set_title(player, fontsize=20)
        ax.spines['left'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(
            which='both',
            bottom=False,
            left=False,
            right=False,
            top=False
        )
        ax.set_xlim((ay_min, ay_max))
        ax.grid(linewidth=0.25)
        ax.get_legend().remove()
        ax.xaxis.set_major_locator(plt.MaxNLocator(3))
        ax.yaxis.set_major_locator(plt.MaxNLocator(6))
        y_labels = ['{:.2f}'.format(x) for x in ax.get_yticks()]
        ax.set_yticklabels(y_labels)

        if team_logo:
            logo_path = selection['logo'].max()
            image = OffsetImage(plt.imread(logo_path), zoom=.2)
            ax.add_artist(AnnotationBbox(image, xy=(0.9,.9), frameon=False, xycoords='axes fraction'))
             
    for ax in axs_list:
        ax.remove()

    #labels and footnotes
    year = df['year'].max()
    week = df['week'].max()
    fig.suptitle(f'{year} Top {axs_list_count} Players By Total Air Yards through Week {week}', fontsize=30, fontweight='bold', y=1.02)
    plt.figtext(0.97, -0.01, 'Data: @NFLfastR\nViz: @MulliganRob', fontsize=14)
    plt.figtext(0.5, -0.01, 'Air Yards', fontsize=20)
    plt.figtext(-0.01, 0.5, 'Density', fontsize=20, rotation='vertical')

    fig.tight_layout()

    if save:
        if team_filter:
            team_str = ('_').join(team_filter)
            fig.savefig(path.join(FIGURE_DIR,f'{year}_Air_Yard_Density_Through{week}_{team_str}.png'), bbox_inches='tight')           
        else:
            fig.savefig(path.join(FIGURE_DIR,f'{year}_Air_Yard_Density_Through{week}.png'), bbox_inches='tight')

def team_scatter_viz(df, x_size=20, y_size=15, save=True):
    """
    Pass teams as index, first column=x, second coluns=y
    """
    df = df.copy()
    logos = df.index.map(nfl_logo_espn_path_map)
    x = df.iloc[:,0]
    y = df.iloc[:,1]
    
    fig, ax = plt.subplots(figsize=(x_size, y_size))
    
    for x0, y0, logo_path in zip(x, y, logos):
        ax.scatter(x0, y0, color='black', s=.001, alpha=0.5)
        image = OffsetImage(plt.imread(logo_path), zoom=.1)
        ax.add_artist(AnnotationBbox(image, xy=(x0,y0), frameon=False, xycoords='data'))
    
    #mean lines
    avg_x = x.mean()
    avg_y = y.mean()  
    ax.axvline(avg_x, linestyle='--', color='black', alpha=0.5)
    ax.axhline(avg_y, linestyle='--', color='black', alpha=0.5)
      
    #axis formatting
    x_col = df.columns[0]
    x_label = x_col.replace('_', ' ').title()
    y_col = df.columns[1]
    y_label = y_col.replace('_', ' ').title()
    ax.tick_params(labelsize=14)
    ax.set_xlabel(x_label, fontsize=16)
    ax.set_ylabel(y_label, fontsize=16)
    ax.grid(zorder=0,alpha=.4)
    
    #figure title
    year = df['year'].max()
    week = df['week'].max()
    fig.suptitle(f'{year} {x_label} and {y_label} through Week {week}', fontsize=30, fontweight='bold', y=1.02)
    plt.figtext(0.92, -0.01, 'Data: @NFLfastR\nViz: @MulliganRob', fontsize=12)
    
    fig.tight_layout()
    
    if save:
        fig.savefig(path.join(FIGURE_DIR,f'{year}_{x_col}_and_{y_col}_through_week_{week}.png'), bbox_inches='tight')
    
def edsr_total_1d_transform(df):
    """
    Calculates the early down success rate and the total number of first downs for each NFL team 
    
    Early Down Success Rate (EDSR) is the percentage of first downs gained before reaching third down. 
    It's basically an efficiency metric tracking the gaining of a first down on first or second down.
    """
    df = df.copy()
    year, week = get_year_and_week(df)
    #edsr
    early_down = df['down'].isin([1,2])
    play_type = (df['play_type'].isin(['pass', 'run'])) & (df['aborted_play'] == 0)
    edsr = (df.loc[early_down & play_type]
              .groupby('posteam')
              .agg(early_down_success_rate=('first_down', 'mean')))
    #first downs per game
    firstdownpg = (df.groupby('posteam')
                     .agg(first_downs=('first_down','sum'),
                          games=('game_id','nunique'))
                     .assign(first_downs_per_game= lambda x: x['first_downs'] / x['games'])
                     .drop(columns=['first_downs','games']))
    return pd.concat([edsr, firstdownpg], axis='columns').assign(year=year).assign(week=week)

def usage_yardline_breakdown_transform(df, player_type='receiver', play='pass'):
    """Calculates the given yardline distribution of opportunities for a given player"""
    year, week = get_year_and_week(df)
    player_id = player_type+'_id'
    play_type = df['play_type'] == str(play)
    #get sort order
    names = (df.groupby([player_id, player_type, 'posteam'], as_index=False)['play_id']
              .count()
              .set_index([player_id, 'posteam'])
              .sort_values('play_id', ascending=False)
              .drop(columns='play_id'))
    names_index = names.index
    yardline_labels = ['1 - 20 yardline', '21 - 40 yardline', '41 - 60 yardline', '61 - 80 yardline', '81 - 100 yardline']
    cut_bins = [-1, 20, 40, 60, 80, 100]
    df = (df.loc[play_type, [player_id, player_type, 'play_id', 'posteam', 'yardline_100']]
               .assign(yardline_100_bin=lambda x: pd.cut(x['yardline_100'], bins=cut_bins, labels=yardline_labels))
               .astype({'yardline_100_bin': 'object'}) #Groupby will also show “unused” categories, which will increase the size of the DF by a lot
               .groupby([player_id, player_type, 'posteam', 'yardline_100_bin']).agg(count=('yardline_100', 'count'))
               .assign(total= lambda x: x.groupby(level=0).transform('sum'))
               .assign(percent=lambda x: (x['count'] / x['total']) * 100)
               .drop(columns=['count', 'total'])
               .unstack()
               .reset_index()
               .set_index([player_id, 'posteam'])
               .set_axis([player_type] + yardline_labels, axis='columns')
               .reindex(names_index)
               .reset_index()
               .drop(columns=player_id)
               .set_index(player_type)
               .fillna(0)
               .assign(year=year)
               .assign(week=week))
    return df

def make_stacked_bar_viz(df, x_size=15, y_size=20, n=25, save=True):
    colors = ['#bc0000', '#808080', '#a9a9a9', '#c0c0c0', '#d3d3d3']
    year = df['year'].max()
    week = df['week'].max()
    player_type = df.index.name.title()
    df = df.drop(columns=['year', 'week', 'posteam']).head(n).copy()

    fig, ax = plt.subplots(figsize=(x_size,y_size))
    df.plot(kind='barh', stacked=True, ax=ax, color=colors, linewidth=1, edgecolor='gray')
    #labels
    for p in ax.patches:
        width, height = p.get_width(), p.get_height()
        if width == 0:
            continue
        x, y = p.get_xy() 
        ax.text(x+width/2, 
                y+height/2, 
                '{:.0f}%'.format(width), 
                horizontalalignment='center', 
                verticalalignment='center')
    ax.legend(ncol=len(df.columns), bbox_to_anchor=(0, -.05),
              loc='lower left', fontsize='medium', handlelength=5)
    # axes formatting
    ax.set_xlim(0, 100)
    ax.xaxis.set_visible(False)
    ax.set_ylabel(player_type)
    ax.tick_params(color='gray', labelcolor='black')
    for spine in ax.spines.values():
        spine.set_edgecolor('gray')
    ax.invert_yaxis()
    #figure title
    fig.suptitle(f'{year} {player_type} Yardline Breakdown through Week {week}', fontsize=30, fontweight='bold', x=0.55, y=1.02, ha='center')
    plt.figtext(0.92, -0.01, 'Data: @NFLfastR\nViz: @MulliganRob', fontsize=12)
    fig.tight_layout()
    if save:
        player_type_lower = player_type.lower()
        fig.savefig(path.join(FIGURE_DIR, f'{year}_through_week_{week}_{player_type_lower}_play_yardline_breakdown.png'), bbox_inches='tight')

def epa_vs_cpoe_transform(df, minimum_att=200):
    """
    Caclulates the average epa per play and average cpoe per play
    epa = expected points added
    cpoe = completion percentage over expected
    """
    df = df.copy()
    year, week = get_year_and_week(df)
    df = (df.groupby(['passer_id','passer'])
            .agg({'posteam': 'last', 'epa':'mean', 'cpoe':'mean', 'play_id':'count'})
            .droplevel(0)
            .assign(year=year)
            .assign(week=week))
    return df.loc[df['play_id']>minimum_att]

def make_epa_vs_cpoe_viz(df, save=True):
    fig, ax = plt.subplots(figsize=(20,15))
    x = df['cpoe']
    y = df['epa']
    size = df['play_id']
    colors = df['posteam'].map(nfl_color_map)
    
    ax.scatter(x, y, s=size, alpha=.7, color=colors)
    #labels
    text = [ax.annotate(name, xy=(x0, y0), alpha=1.0, zorder=2) for name, x0, y0 
        in zip(df.index, x, y)]
    adjust_text(text)
    #mean lines
    avg_x = x.mean()
    avg_y = y.mean()  
    ax.axvline(avg_x, linestyle='--', color='gray')
    ax.axhline(avg_y, linestyle='--', color='gray')
    #title
    year = df['year'].max()
    week = df['week'].max()
    ax.set_title(f'{year} CPOE vs EPA (Through Week {week})', fontsize=16, fontweight='bold')
    #labels
    ax.set_xlabel('Completion % Over Expected (CPOE)',fontsize=16,labelpad=15)
    ax.set_ylabel('EPA per Attempt',fontsize=16,labelpad=15)
    #Add grid
    ax.grid(zorder=0,alpha=.4)
    ax.set_axisbelow(True)
    #Remove top and right boundary lines
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    #margins and footnotes
    #ax.margins(x=.05, y=.01)
    ax.annotate('Data: @NFLfastR',xy=(.90,-0.05), fontsize=12, xycoords='axes fraction')
    ax.annotate('Figure: @MulliganRob',xy=(.90,-0.07), fontsize=12, xycoords='axes fraction')
    if save:
        fig.savefig(path.join(FIGURE_DIR, f'{year}_through_week_{week}_cpoe_vs_epa.png'), bbox_inches='tight')

def neutral_pass_rate_transform(df):
    """
    Caclulates the percentage that each team throws in neutral situations
    Neutral situation is defined as between 20% and 80% win probability, either 1st or 2nd down, 
    and outside of two minutes remaining in each half
    """
    df = df.copy()
    year, week = get_year_and_week(df)
    downs = df['down'] < 3
    time = df['half_seconds_remaining'] >120
    wp_low = df['wp'] >= .2
    wp_high = df['wp'] <= .8
    df = (df.loc[downs & time & wp_low & wp_high]
            .groupby('posteam')['pass'].mean()
            .to_frame()
            .assign(year=year)
            .assign(week=week)
            .sort_values('pass', ascending=False))
    return df

def make_neutral_pass_rate_viz(df):
    fig, ax = plt.subplots(figsize=(30,15))
    color = df.index.map(nfl_color_map)
    logo = df.index.map(nfl_logo_espn_path_map)
    images = [OffsetImage(plt.imread(logo_path), zoom=.1) for logo_path in logo]
    x = df.index
    y = df['pass']
    ax.bar(x, y, color=color, width=0.5)
    
    for x0, y0, im in zip(x, y, images):
        ax.add_artist(AnnotationBbox(im, xy=(x0,y0), frameon=False, xycoords='data'))
    
    #Add league average line
    ax.axhline(y=y.mean(),linestyle='--',color='black')

    #Add grid
    ax.grid(zorder=0,alpha=.6,axis='y')
    ax.set_axisbelow(True)
    
    #title
    year = df['year'].max()
    week = df['week'].max()
    ax.set_title(f'{year} Neutral Pass Rate (Through Week {week})\n 1st & 2nd Down, Win Prob. Between 20-80%, Final Two Minutes Excluded',
                fontsize=25, fontweight='bold', pad=20)
    
    #axis label
    ax.set_ylabel('Pass Rate',fontsize=20,labelpad=20)
    ax.tick_params(labelsize=16)
    
    #League average line label
    plt.text(30.5,.53,'NFL Average',fontsize=14)
    
    #footnotes
    ax.annotate('Data: @NFLfastR',xy=(.90,-0.05), fontsize=12, xycoords='axes fraction')
    ax.annotate('Figure: @MulliganRob',xy=(.90,-0.07), fontsize=12, xycoords='axes fraction');

def second_and_long_pass_transform(df):
    """Calculates the percentage that each team passes on 2nd down and long (>8 yards)"""
    df = df.copy()
    year, week = get_year_and_week(df)
    downs = df['down'] == 2
    time = df['half_seconds_remaining'] >120
    wp_low = df['wp'] >= .2
    wp_high = df['wp'] <= .8
    to_go = df['ydstogo'] >= 8
    df = (df.loc[downs & time & wp_low & wp_high & to_go]
            .groupby('posteam')['pass'].mean()
            .to_frame()
            .assign(year=year)
            .assign(week=week)
            .sort_values('pass', ascending=False)
         )
    return df

def make_second_and_long_pass_rate_viz(df, color='team'):
    fig, ax = plt.subplots(figsize=(30,20))
    if color == 'team':
        color = df.index.map(nfl_color_map)
    else:
        color = cm.get_cmap(color)
        color = color(np.linspace(0,.8,len(df)))
    logo = df.index.map(nfl_logo_espn_path_map)
    images = [OffsetImage(plt.imread(logo_path), zoom=.1) for logo_path in logo]
    x = df.index
    y = df['pass']
    ax.barh(x, y, color=color, height=0.5)
    
    for x0, y0, im in zip(x, y, images):
        ax.add_artist(AnnotationBbox(im, xy=(y0,x0), frameon=False, xycoords='data'))
    
    #Add league average line
    ax.axvline(x=y.mean(),linestyle='--',color='black')

    #Add grid
    ax.grid(zorder=0,alpha=.6,axis='x')
    ax.set_axisbelow(True)
    
    #title
    year = df['year'].max()
    week = df['week'].max()
    ax.set_title(f'{year} Second and Long Pass Rate (Through Week {week})\n2nd and 8+ To Go, Win Prob. Between 20-80%, Final Two Minutes Excluded',
                fontsize=25, fontweight='bold', pad=20)
    #axis label
    ax.set_xlabel('Pass Rate',fontsize=20,labelpad=20)
    ax.tick_params(labelsize=16)
    ax.invert_yaxis()
    ax.margins(x=.05, y=.001)
    
    #League average line label
    plt.text(y.mean() + 0.005, 30.5, 'NFL Average',fontsize=14)
    
    #footnotes
    ax.annotate('Data: @NFLfastR\nFigure: @MulliganRob',xy=(.90,-0.05), fontsize=14, xycoords='axes fraction')
    
    fig.tight_layout()
    fig.savefig(f'{year}_Second_and_Long_Pass_Rate_{week}.png', bbox_inches='tight')

def epa_transform(df, *play_type, col='posteam', rank=True):
    """Returns a series of avg EPA per play for either the posteam or defteam"""
    play_type_list=[str(play) for play in play_type]
    df = df.copy()
    play_type = df['play_type'].isin(play_type_list)
    epa_flag = df['epa'].isna() == False
    ser = (df.loc[play_type & epa_flag]
            .groupby(col)['epa']
            .mean())
    if rank:
        return ser.rank(ascending=False, method='min') if  col=='posteam' else ser.rank(method='min')
    else:
        return ser

def sack_rate_transform(df, col='posteam', rank=True):
    """Returns a series of avg sack rate per pass play for either the posteam or defteam"""
    df = df.copy()
    play_type = df['play_type'] == 'pass'
    ser =  (df.loc[play_type]
             .groupby(col)['sack']
             .mean()
             .mul(100))
    if rank:
        return ser.rank(method='min') if col=='posteam' else ser.rank(ascending=False, method='min')
    else:
        return ser

def neutral_pace_transform(df, rank=True, col='posteam', time=120, wp_low=0.2, wp_high=0.8):
    """Returns a series of avg plays per game for either the posteam or defteam"""
    df = df.copy()
    time = df['half_seconds_remaining'] > time
    wp_low = df['wp'] >= wp_low
    wp_high = df['wp'] <= wp_high
    play_type = df['play_type'].isin(['pass', 'run'])
    df = (df.loc[time & wp_low & wp_high & play_type]
            .groupby(col)
            .agg(plays=('play_id', 'count'), games=('game_id', 'nunique'))
            .assign(neutral_pace = lambda x: x['plays'] / x['games'])
            .drop(columns=['plays', 'games']))
    if rank:
        return df.rank(ascending=False, method='min').squeeze() if col=='posteam' else df.rank(method='min').squeeze()
    else:
        return df.squeeze()

def offense_vs_defense_transform(df, rank=True):
    """
    Brings together offesnive and defesnive pass/rush epa, dack rate, plays per game
    Specify rank=False if you want the actrual values of each stat
    """
    #pass o vs d
    pass_epa_off = epa_transform(df, 'pass', col='posteam', rank=rank).to_frame().assign(unit='offense').set_index('unit', append=True)
    pass_epa_def = epa_transform(df, 'pass', col='defteam', rank=rank).to_frame().assign(unit='defense').set_index('unit', append=True)
    pass_epa = pd.concat([pass_epa_off, pass_epa_def]).rename(columns={'epa':'pass_epa'})
    
    #rush o vs d
    run_epa_off = epa_transform(df, 'run', col='posteam', rank=rank).to_frame().assign(unit='offense').set_index('unit', append=True)
    run_epa_def = epa_transform(df, 'run', col='defteam', rank=rank).to_frame().assign(unit='defense').set_index('unit', append=True)
    run_epa = pd.concat([run_epa_off, run_epa_def]).rename(columns={'epa':'rush_epa'})
    
    #off sack rate o vs d
    off_sack = sack_rate_transform(df, col='posteam', rank=rank).to_frame().assign(unit='offense').set_index('unit', append=True)
    def_sack = sack_rate_transform(df, col='defteam', rank=rank).to_frame().assign(unit='defense').set_index('unit', append=True)
    sack = pd.concat([off_sack, def_sack])

    #pace o vs d
    off_pace = neutral_pace_transform(df, col='posteam', rank=rank).to_frame().assign(unit='offense').set_index('unit', append=True)
    def_pace = neutral_pace_transform(df, col='defteam', rank=rank).to_frame().assign(unit='defense').set_index('unit', append=True)
    pace = pd.concat([off_pace, def_pace])
    
    return pd.concat([pass_epa, run_epa, sack, pace], axis='columns')

def receiver_summary_table(df):
    """
    Displays a summary table of WR-related statistics derived from play-by-play data
    """
    df = df.copy()
    team_logo = get_team_colors_and_logos_dataframe().loc[:,['team_logo_espn', 'team_abbr']]
    team_logo['team_logo_espn'] = team_logo['team_logo_espn'].apply(lambda x: f'<img src="{x}" width="50px">')                                              
    play_type = df['play_type'] == 'pass'
    df = (df.loc[play_type]
            .assign(ez_tgts= lambda x: (x['air_yards']==x['yardline_100']))
            .groupby(['receiver_id', 'receiver'])
            .agg(posteam=('posteam', 'last'),
                games=('game_id', 'nunique'),
                air_yards=('air_yards', 'sum'),
                adot=('air_yards', 'mean'),
                rec=('complete_pass', 'sum'),
                rec_yards=('yards_gained', 'sum'),
                targets=('play_id', 'count'),
                rec_tds=('pass_touchdown', 'sum'),
                rz_tgts=('yardline_100', lambda x: (x <= 20).sum()),
                ez_tgts=('ez_tgts', 'sum'))
            .assign(target_share= lambda x: x['targets'] / x.groupby('posteam')['targets'].transform('sum') * 100,
                    yards_per_rec= lambda x: x['rec_yards'] / x['rec'],
                    ay_share= lambda x: x['air_yards'] / x.groupby('posteam')['air_yards'].transform('sum') * 100,
                    ay_pg= lambda x: x['air_yards'] / x['games'],
                    catch_rate= lambda x: x['rec']/x['targets'] * 100,
                    ppr_pts= lambda x: x['rec']*1 + x['rec_yards']*0.1 + x['rec_tds']*6,
                    rz_tgt_pg= lambda x: x['rz_tgts'] / x['games'],
                    ez_tgt_pg= lambda x: x['ez_tgts'] / x['games'],
                    rec_tds_pg= lambda x: x['rec_tds'] / x['games'])
          .sort_values('ppr_pts', ascending=False)
          .reset_index()
          .merge(team_logo, left_on='posteam', right_on='team_abbr', how='left')
          .drop(columns='receiver_id')
          .set_index('receiver')
          .round(2)
          .drop(columns=['games', 'air_yards', 'rec', 'rec_yards', 'rz_tgts', 'ez_tgts'])
          .rename(columns={'team_logo_espn': 'team'})
         )
    columns = ['team', 'targets', 'adot', 'ay_share', 'ay_pg', 
               'catch_rate', 'target_share', 'yards_per_rec', 
                  'rz_tgt_pg', 'ez_tgt_pg', 'rec_tds_pg', 'rec_tds', 'ppr_pts']
    return df.loc[:,columns]

def running_back_summary_table(df, minimum_attempts=100):
    """
    Displays a summary table of RB-related statistics derived from play-by-play data, with a focus on PPR leagues
    """
    df = df.copy()
    team_logo = get_team_colors_and_logos_dataframe().loc[:,['team_logo_espn', 'team_abbr']]
    team_logo['team_logo_espn'] = team_logo['team_logo_espn'].apply(lambda x: f'<img src="{x}" width="50px">')
    #wr to join to rush stats
    pass_play = df['play_type'] == 'pass'
    wr_table = (df.loc[pass_play].groupby(['receiver_id', 'receiver'])
                                 .agg(rec=('complete_pass', 'sum'), 
                                      rec_tds=('pass_touchdown', 'sum'),
                                      rec_yards=('yards_gained', 'sum'))
                                 .rename_axis(['rusher_id', 'rusher']))
    play_type = df['play_type'] == 'run'
    df = (df.loc[play_type]
            .groupby(['rusher_id', 'rusher'])
            .agg(posteam=('posteam', 'last'),
                games=('game_id', 'nunique'),
                attempts=('play_id', 'count'),
                rush_yards=('yards_gained', 'sum'),
                rush_tds=('rush_touchdown', 'sum'),
                pos_run_rate=('yards_gained', lambda x: (x > 0).mean() * 100),
                att_5_yd_rate=('yardline_100', lambda x: (x <= 5).mean() * 100))
            .merge(wr_table, how='left', left_index=True, right_index=True)
            .assign(total_tds= lambda x: x['rush_tds'] + x['rec_tds'],
                    carry_share= lambda x: x['attempts'] / x.groupby('posteam')['attempts'].transform('sum') * 100,
                    yards_share= lambda x: x['rush_yards'] / x.groupby('posteam')['rush_yards'].transform('sum') * 100,
                    ypc= lambda x: x['rush_yards'] / x['attempts'],
                    td_rate= lambda x: x['rush_tds'] / x['attempts'] * 100,
                    ppr_pts= lambda x: x['rec'] + x['rush_yards']*0.1 + x['rec_yards']*0.1 + x['total_tds']*6,
                    rec_pg = lambda x: x['rec'] / x['games'],
                    rush_td_pg = lambda x: x['rush_tds'] / x['games'],
                    rec_td_pg = lambda x: x['rec_tds'] / x['games']
                    )
          .sort_values('ppr_pts', ascending=False)
          .reset_index()
          .merge(team_logo, left_on='posteam', right_on='team_abbr', how='left')
          .drop(columns=['rusher_id', 'rush_yards', 'rec', 'rush_tds', 'rec_tds'])
          .set_index('rusher')
          .round(2)
          .drop(columns=['games'])
          .rename(columns={'team_logo_espn': 'team'})
         )
    columns = ['team', 'attempts', 'carry_share', 'yards_share', 'ypc', 'td_rate', 'pos_run_rate', 'att_5_yd_rate', 
              'rec_pg', 'rec_td_pg', 'rush_td_pg', 'total_tds', 'ppr_pts']
    return df.loc[df['attempts'] >= minimum_attempts,columns]

def quarterback_summary_table(df, minimum_attempts=200):
    """
    Displays a summary table of QB-related statistics derived from play-by-play data
    """
    df = df.copy()
    team_logo = get_team_colors_and_logos_dataframe().loc[:,['team_logo_espn', 'team_abbr']]
    team_logo['team_logo_espn'] = team_logo['team_logo_espn'].apply(lambda x: f'<img src="{x}" width="50px">')
    #conditions
    passer = ~df['passer'].isna()
    run_play = df['play_type'] == 'run'
    pass_play = df['play_type'] == 'pass'
    qb_kneel = df['play_type'] == 'qb_kneel'
    no_sack = df['sack'] == 0
    #rushing stats to join to passing stats
    rb_table = (df.loc[run_play | qb_kneel].groupby(['rusher_id', 'rusher'])
                                 .agg(rush_tds=('rush_touchdown', 'sum'),
                                      rush_yards=('yards_gained', 'sum'),
                                     rush_attempts=('play_id', 'count'),
                                     rush_epa=('epa', 'sum'))
                                 .rename_axis(['passer_id', 'passer']))
    #passing df
    df = (df.assign(scramble_yds= lambda x: x['yards_gained'].where(passer & run_play & no_sack),
                    pass_yards= lambda x: x['yards_gained'].where(passer & pass_play  & no_sack),
                    scramble_tds= lambda x: x['rush_touchdown'].where(passer & run_play),
                    scramble_attempts= lambda x: x['play_id'].where(passer & run_play),
                    scramble_epa= lambda x: x['epa'].where(passer & run_play),
                    pass_epa= lambda x: x['epa'].where(passer & pass_play  & no_sack),
                    pass_tds= lambda x: x['pass_touchdown'].where(passer & pass_play),
                    pass_attempts= lambda x: x['play_id'].where(pass_play))
            .groupby(['passer_id','passer'])
            .agg(posteam=('posteam','last'),
                games=('game_id','nunique'),
                pass_attempts=('pass_attempts','count'),
                pass_yards=('pass_yards','sum'),
                scramble_yds=('scramble_yds','sum'),
                scramble_attempts=('scramble_attempts', 'count'),
                scramble_epa=('scramble_epa', 'sum'),
                pass_tds=('pass_tds','sum'),
                scramble_tds=('scramble_tds','sum'), 
                pass_epa=('pass_epa','sum'),
                interception=('interception','sum'))
            .merge(rb_table, how='left', left_index=True, right_index=True)
            .assign(total_tds= lambda x: x['rush_tds'] + x['pass_tds'] + x['scramble_tds'],
                    ppr_pts= lambda x: x['rush_yards']*0.1 + x['pass_yards']*0.04 + x['total_tds']*6,
                    ppr_pts_pg= lambda x: x['ppr_pts'] / x['games'],
                    rush_tds= lambda x: x['rush_tds'] + x['scramble_tds'],
                    rush_yards= lambda x: x['rush_yards'] + x['scramble_yds'],
                    total_yards_pg= lambda x: (x['rush_yards'] + x['pass_yards']) / x['games'],
                    epa_pg= lambda x: (x['rush_epa'] + x['scramble_epa'] + x['pass_epa']) / (x['games'])
                    )
           .sort_values('ppr_pts', ascending=False)
           .reset_index()
           .merge(team_logo, left_on='posteam', right_on='team_abbr', how='left')
           .set_index('passer')
           .round(2)
           .rename(columns={'team_logo_espn': 'team', 'interception': 'int'})
         )
    columns = ['team', 'pass_yards', 'pass_tds', 'rush_yards', 'rush_tds', 'total_tds', 
               'int', 'total_yards_pg', 'epa_pg', 'ppr_pts_pg', 'ppr_pts']
    return df.loc[df['pass_attempts']>minimum_attempts, columns]

def set_selectors_and_props():
    """Set specific visual attributes for RB Style table
    selector is based on HTML elements and CSS properties"""
    return [dict(selector='caption',
                 props=[('color', 'black'), ('background-color', 'white'), ('font-size', '16px'), ('text-align', 'center'),('font-weight', 'bold')]),
            dict(selector='th',
                 props=[('color', 'black')])]

def hover_data(hover_color='gray'):
    return dict(selector='td:hover',
                props=[('background-color', '%s' % hover_color)])

def hover_rows(hover_color='gray'):
    return dict(selector='tr:hover',
                props=[('background-color', '%s' % hover_color)])

def table_styler(df, pos, n=20, caption='Top Players', color='green', save=False):
    df = df.copy()
    df.index.name = None
    cm = sns.light_palette(color, as_cmap=True)
    styled_df = (df.head(n).style
                        .background_gradient(cmap=cm)
                        .set_caption(caption))
    if pos =='RB':
        styled_df = (styled_df.format('{0:,.1f}%', subset=['pos_run_rate','carry_share', 'td_rate', 'att_5_yd_rate', 'yards_share'])
                              .format('{0:,.1f}', subset=['ypc', 'rec_pg', 'rec_td_pg', 'rush_td_pg', 'ppr_pts'])
                              .format('{0:,.0f}', subset=['total_tds', 'attempts']))
    elif pos =='WR':
        styled_df = (styled_df.format('{0:,.1f}%', subset=['ay_share','catch_rate', 'target_share'])
                              .format('{0:,.1f}', subset=['adot', 'ay_pg','yards_per_rec', 'ppr_pts', 'rz_tgt_pg', 'ez_tgt_pg', 'rec_tds_pg'])
                              .format('{0:,.0f}', subset=['targets', 'rec_tds']))
    elif pos=='QB':
        styled_df = (styled_df.format('{0:,.1f}', subset=['rush_yards', 'ppr_pts_pg', 'ppr_pts', 'epa_pg', 'total_yards_pg'])
                              .format('{0:,.0f}', subset=['pass_yards', 'pass_tds', 'rush_yards', 'rush_tds', 'total_tds', 'int']))
    styled_df = styled_df.set_table_styles(set_selectors_and_props())
    if save:
        caption_name = '_'.join(caption.split())
        dfi.export(styled_df, f'{caption_name}.png')
    return HTML(styled_df.render())

columns = ['team', 'pass_yards', 'pass_tds', 'rush_yards', 'rush_tds', 'total_tds', 
               'int', 'epa_pg', 'ppr_pts_pg', 'ppr_pts']

def team_rec_yards_transform(df):
    year, week = get_year_and_week(df)
    play_type = df['play_type'] == 'pass'
    return (df.loc[play_type]
             .groupby(['posteam', 'play_id'])
             .agg(rec_yards=('yards_gained','sum'))
             .droplevel(1)
             .assign(year=year)
             .assign(week=week)
            )

def team_yards_gained_transform(df):
    year, week = get_year_and_week(df)
    play_type = (df['play_type'].isin(['pass', 'run'])) & (df['aborted_play'] == 0)
    return (df.loc[play_type]
             .groupby(['posteam', 'play_id'])
             .agg(yards_gained=('yards_gained','sum'),
                  play_type=('play_type', 'first'))
             .droplevel(1)
             .assign(year=year)
            .assign(week=week)
            .sort_values('play_type')
            )

def make_team_swarm(df, save=True, y_lim_min=-10, ylim_max=100):
    fig, axs = plt.subplots(4, 8, figsize=(20,25), sharex=True)
    team_list = sorted(df.index.drop_duplicates())
    axs_list = [item for sublist in axs for item in sublist] 
    
    for team, ax in zip(team_list, axs_list):
        sns.swarmplot(df.loc[df.index==team, df.columns[0]], 
                    ax=ax, color=nfl_color_map[team])
        
        #formatting
        ax.spines['left'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.tick_params(
            which='both',
            bottom=False,
            left=False,
            right=False,
            top=False
        )
        ax.set_xlabel(None)
        ax.set_xlim(y_lim_min, ylim_max)
        #Add grid
        ax.grid(zorder=0,alpha=.4)
        ax.set_axisbelow(True)
        
        # word marks
        logo_path = nfl_wordmark_path_map[team]
        image = OffsetImage(plt.imread(logo_path), zoom=.5)
        ax.add_artist(AnnotationBbox(image, xy=(0.5,1.0), frameon=False, xycoords='axes fraction'))
    
    fig.tight_layout()

    #title
    col_name = df.columns[0].title().replace('_', ' ')
    year = df['year'].max()
    week = df['week'].max()
    fig.suptitle(f'{year} {col_name} Team By Team Distribution (Through Week {week})', fontsize=30, fontweight='bold', x=0.5, y=1.05, ha='center')
    plt.figtext(0.92, -0.03, 'Data: @NFLfastR\nViz: @MulliganRob', fontsize=12)

    if save:
        col_name_lower = col_name.lower().replace(' ', '_')
        fig.savefig(path.join(FIGURE_DIR, f'{year}_through_week_{week}_{col_name_lower}_swarmplot.png'), bbox_inches='tight')

def make_team_kde(df, save=True):
    fig, axs = plt.subplots(4, 8, figsize=(20,15), sharey=True)
    team_list = sorted(df.index.drop_duplicates())
    axs_list = [item for sublist in axs for item in sublist] 
    
    for team, ax in zip(team_list, axs_list):
        sns.kdeplot(df.loc[df.index==team, df.columns[0]], 
                    ax=ax, linewidth=3.0, color=nfl_color_map[team], 
                    shade=True, clip=[-5, 50])
        ax.get_legend().remove()
        
        #formatting
        ax.spines['left'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(
            which='both',
            bottom=False,
            left=False,
            right=False,
            top=False
        )
        #Add grid
        ax.grid(zorder=0,alpha=.4)
        ax.set_axisbelow(True)
        
        # word marks
        logo_path = nfl_wordmark_path_map[team]
        image = OffsetImage(plt.imread(logo_path), zoom=.5)
        ax.add_artist(AnnotationBbox(image, xy=(0.5,1.0), frameon=False, xycoords='axes fraction'))
    
    fig.tight_layout()
    #title
    col_name = df.columns[0].title().replace('_', ' ')
    year = df['year'].max()
    week = df['week'].max()
    fig.suptitle(f'{year} {col_name} Team By Team Distribution (Through Week {week})', fontsize=30, fontweight='bold', x=0.5, y=1.05, ha='center')
    plt.figtext(0.92, -0.03, 'Data: @NFLfastR\nViz: @MulliganRob', fontsize=12)

    if save:
        col_name_lower = col_name.lower().replace(' ', '_')
        fig.savefig(path.join(FIGURE_DIR, f'{year}_through_week_{week}_{col_name_lower}_kdeplot.png'), bbox_inches='tight')

def make_team_jitter(df, save=True, play_type=False, y_lim_min=-10, ylim_max=60):
    fig, axs = plt.subplots(4, 8, figsize=(20,25), sharey=True)
    team_list = sorted(df.index.drop_duplicates())
    axs_list = [item for sublist in axs for item in sublist] 
    
    for team, ax in zip(team_list, axs_list):
        if play_type:
            sns.stripplot(x=df.loc[df.index==team, 'play_type'], y=df.loc[df.index==team, df.columns[0]], 
                    ax=ax, jitter=True, alpha=0.5, size=7,  palette=[nfl_color_map[team], nfl_color_map_secondary[team]],
                     dodge=True)
        else:
            sns.stripplot(y=df.loc[df.index==team, df.columns[0]], 
                        ax=ax, color=nfl_color_map[team], jitter=1.05, alpha=0.5, size=7)
            
        #formatting
        ax.spines['left'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.tick_params(
            which='both',
            bottom=False,
            left=False,
            right=False,
            top=False
        )
        ax.set_ylabel(None)
        ax.set_xlabel(None)
        ax.set_ylim(y_lim_min, ylim_max)
        #Add grid
        ax.grid(zorder=0,alpha=.4)
        ax.set_axisbelow(True)
        
        # word marks
        logo_path = nfl_wordmark_path_map[team]
        image = OffsetImage(plt.imread(logo_path), zoom=.5)
        ax.add_artist(AnnotationBbox(image, xy=(0.6,1.0), frameon=False, xycoords='axes fraction'))
    
    fig.tight_layout()

    #title
    col_name = df.columns[0].title().replace('_', ' ')
    year = df['year'].max()
    week = df['week'].max()
    fig.suptitle(f'{year} {col_name} Team By Team Distribution (Through Week {week})', fontsize=30, fontweight='bold', x=0.5, y=1.05, ha='center')
    plt.figtext(0.92, -0.03, 'Data: @NFLfastR\nViz: @MulliganRob', fontsize=12)

    if save:
        col_name_lower = col_name.lower().replace(' ', '_')
        fig.savefig(path.join(FIGURE_DIR, f'{year}_through_week_{week}_{col_name_lower}_jitterplot.png'), bbox_inches='tight')