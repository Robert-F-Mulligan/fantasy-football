# nflfastrfuncs.py

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib import cm
import fantasyfootball
from os import path
from fantasyfootball.config import DATA_DIR, FIGURE_DIR, pfr_to_fantpros, nfl_color_map, nfl_logo_espn_path_map
import seaborn as sns
import numpy as np
from adjustText import adjust_text
import requests
from io import BytesIO
import codecs
import urllib.request
from datetime import datetime

def get_nfl_fast_r_data(*years):
    """Retrives play by play data from the NFLfastr git repo for a given year(s) """
    df_list = [pd.read_csv('https://github.com/guga31bb/nflfastR-data/blob/master/data/' \
                            'play_by_play_' + str(year) + '.csv.gz?raw=True',
                            compression='gzip', low_memory=False)
              for year in years]
    return pd.concat(df_list)

def get_nfl_fast_r_roster_data(*years):
    """Retrives NFL roster data from the NFLfastr git repo for a given year(s) """
    df = pd.read_csv('https://github.com/guga31bb/nflfastR-data/blob/master/roster-data/' \
                            'roster.csv.gz?raw=true', compression='gzip', low_memory=False)
    if len(years) > 0:
        years = [str(year) for year in years]
        df = df.loc[df['team.season'].isin(years)]
    #df = df.loc[df['teamPlayers.status'] == 'ACT']
    return df

def get_nfl_fast_r_roster_data_decoded(year=2020):
    df = pd.read_csv(f'https://github.com/mrcaseb/nflfastR-roster/blob/master/data/seasons/roster_{year}.csv?raw=true', low_memory=False)
    return df

def convert_to_gsis_id(new_id):
    """Apply this function to nflfastr play-by-play in order to join to 2020 roster data gsis_id """
    if type(new_id) == float:
        return new_id  
    return codecs.decode(new_id[4:-8].replace('-',''),"hex").decode('utf-8')

def get_year_and_week(df):
    """Extracts season and max week in an NFLfastr df; useful for labeling figures """
    year = datetime.strptime(df['game_id'].str.split('_').str[0].max(), '%Y')
    week = df['week'].max()
    return year, week

def save_team_images(column='team_wordmark'):
    """Fucntion will loop through a dataframe column and save URL images locally"""
    df = pd.read_csv(r'https://github.com/guga31bb/nflfastR-data/raw/master/teams_colors_logos.csv')
    my_series = df[column]
    my_list = my_series.to_list()
    for im_url in my_list:
        image_url = im_url
        filename = image_url.split("/")[-1]
        local_path = r'..\figures'
        file_path = path.join(local_path, filename)
        urllib.request.urlretrieve(image_url, file_path)

def target_share_vs_air_yard_share_transform(df):
    """Calculates the team target share and total air yards for a given receiver """
    df = df.copy()
    year, week = get_year_and_week
    play_type = df['play_type'] == 'pass'
    df =  (df.loc[play_type].copy()
            .groupby(['receiver_id', 'receiver', 'posteam'])
            .agg(targets=('play_type', 'count'), air_yards=('air_yards', 'sum'))
            .sort_values('targets', ascending=False)
            .assign(team_targets= lambda x: x.groupby('posteam')['targets'].transform('sum'))
            .assign(team_air_yards=lambda x: x.groupby('posteam')['air_yards'].transform('sum'))
            .assign(target_share=lambda x: x['targets'] / x['team_targets'])
            .assign(air_yard_share=lambda x: x['air_yards'] / x['team_air_yards'])
            .assign(year=year)
            .assign(week=week)
            .droplevel(0)
            .reset_index()
            .set_index('receiver'))
    return df

def target_share_vs_air_yard_share_viz(df, *team_filter, n=60, x_size=20, y_size=15, save=True):
    if len(team_filter) > 0:
        team_list = [team for team in team_filter]
        df = df.loc[df['posteam'].isin(team_list)].copy()
    else:
        df = df.head(n).copy()
    sns.set_style('whitegrid');
    df['color'] = df['posteam'].map(nfl_color_map)
    fig, ax = plt.subplots(figsize=(x_size, y_size))
    ax.scatter(df['target_share'], df['air_yard_share'], color=df['color'], alpha=1.0)
    text = [ax.annotate(name, xy=(x+.001, y), alpha=1.0, zorder=2) for name, x, y 
        in zip(df.index, df['target_share'], df['air_yard_share'])]
    adjust_text(text)
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
    """Calculates total carries a rusher has inside the 5 yardline """
    df = df.copy()
    year, week = get_year_and_week(df)
    play_type = df['play_type']=='run'
    inside_5 = df['yardline_100']<5
    df = (df.loc[play_type & inside_5]
            .groupby(['rusher_id', 'rusher', 'posteam'])[['play_id']]
            .count()
            .sort_values(by=['play_id'],ascending=False)
            .droplevel(0)
            .reset_index()
            .set_index('rusher')
            .assign(year=year)
            .assign(week=week))
    return df

def carries_inside_5_yardline_viz(df, *team_filter, n=20, x_size=20, y_size=15, save=True):
    if len(team_filter) > 0:
        team_list = [team for team in team_filter]
        df = df.loc[df['posteam'].isin(team_list)].copy()
    else:
        df = df.head(n).copy()
    #color and logo mapping
    df['color'] = df['posteam'].map(nfl_color_map)
    df['logo'] = df['posteam'].map(nfl_logo_espn_path_map)
    sns.set_style('whitegrid');
    fig,ax = plt.subplots(figsize=(x_size, y_size))
    ax.barh(df.index, df['play_id'], color=df['color'])
    for carries, x, y in zip(df['play_id'], df['play_id'], df.index):
        ax.annotate(carries, xy=(x, y), fontsize=12)
    images = [OffsetImage(plt.imread(file_path), zoom=.1) for file_path in df['logo'].to_list()]
    x0 = [(df['play_id'].max() * 0.02)] * len(df['play_id'])
    for im, x, y in zip(images, x0, df.index):
        ax.add_artist(AnnotationBbox(im, xy=(x,y), frameon=False, xycoords='data'))
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
            .groupby(['receiver_id', 'receiver', 'posteam', 'play_id'])['air_yards'].sum()
            .to_frame()
            .assign(total_air_yards= lambda x: x.groupby(['receiver_id']).transform('sum'))
            .sort_values(['total_air_yards', 'receiver_id', 'posteam'], ascending=False)
            .drop(columns='total_air_yards')
            .droplevel(0)
            .reset_index()
            .drop(columns='play_id')
            .assign(colors= lambda x: x['posteam'].map(nfl_color_map))
            .assign(logo= lambda x: x['posteam'].map(nfl_logo_espn_path_map))
            .assign(year=year)
            .assign(week=week))
    return df

def air_yard_density_viz(df, *team_filter, x_size=30, y_size=35, team_logo=True, save=True):
    if len(team_filter) > 0:
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

def team_scatter_viz(df, x_size=20, y_size=10, save=True):
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
    ax.set_xlabel(x_label, fontsize=12)
    ax.set_ylabel(y_label, fontsize=12)
    ax.grid(zorder=0,alpha=.4)
    
    #figure title
    year = df['year'].max()
    week = df['week'].max()
    fig.suptitle(f'{year} {x_label} and {y_label} through Week {week}', fontsize=30, fontweight='bold', y=1.05)
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
    #first downs per game
    first_downs = df.groupby(['posteam'])['first_down'].agg(first_downs_per_game=('first_down', 'sum'))
    game_count = df.groupby(['posteam'])['game_id'].agg(first_downs_per_game=('first_down', 'nunique'))
    first_downs_per_game = first_downs / game_count
    #edsr
    early_down = df['down'].isin([1,2])
    play_type = (df['play_type'].isin(['pass', 'run'])) & (df['aborted_play'] == 0)
    early_down_success = df.loc[early_down & play_type].groupby('posteam')['first_down'].agg(early_down_success_rate=('first_down', 'mean'))
    scatter_df = pd.merge(early_down_success, first_downs_per_game, left_index=True, right_index=True)
    scatter_df = (scatter_df.assign(year=year)
                            .assign(week=week))
    return scatter_df

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
               .astype({'yardline_100_bin': 'object'}) #convert from categorical to allow groupby to work more efficiently
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
    df = (df.groupby(['passer_id','passer', 'posteam'])
            .agg({'epa':'mean', 'cpoe':'mean', 'play_id':'count'})
            .droplevel(0)
            .reset_index()
            .set_index('passer')
            .assign(year=year)
            .assign(week=week))
    return df.loc[df['play_id']>minimum_att]

def make_epa_vs_cpoe_viz(df, save=True):
    fig, ax = plt.subplots(figsize=(15,15))
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
            .groupby('posteam', as_index=False)['pass'].mean()
            .assign(year=year)
            .assign(week=week)
            .set_index('posteam')
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
            .groupby('posteam', as_index=False)['pass'].mean()
            .assign(year=year)
            .assign(week=week)
            .set_index('posteam')
            .sort_values('pass', ascending=False)
         )
    return df

def make_second_and_long_pass_rate_viz(df, color='team'):
    fig, ax = plt.subplots(figsize=(40,15))
    if color == 'team':
        color = df.index.map(nfl_color_map)
    else:
        color = cm.color(np.linspace(0,.8,len(df)))
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
    ax.annotate('Data: @NFLfastR',xy=(.90,-0.05), fontsize=12, xycoords='axes fraction')
    ax.annotate('Figure: @MulliganRob',xy=(.90,-0.07), fontsize=12, xycoords='axes fraction');
    
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

