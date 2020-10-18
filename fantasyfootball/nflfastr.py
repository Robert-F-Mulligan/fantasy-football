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
from adjustText import adjust_text
import requests
from io import BytesIO


def get_nfl_fast_r_data(*years):
    df = pd.DataFrame()
    for year in years:
        year_df = pd.read_csv('https://github.com/guga31bb/nflfastR-data/blob/master/data/' \
                            'play_by_play_' + str(year) + '.csv.gz?raw=True',
                            compression='gzip', low_memory=False)
        df = df.append(year_df, sort=True)
    return df

def get_nfl_fast_r_roster_data(*years):
    df = pd.read_csv('https://github.com/guga31bb/nflfastR-data/blob/master/roster-data/' \
                            'roster.csv.gz?raw=true', compression='gzip', low_memory=False)
    if len(years) > 0:
        years = [str(year) for year in years]
        df = df.loc[df['team.season'].isin(years)]
    #df = df.loc[df['teamPlayers.status'] == 'ACT']
    return df

def target_share_vs_air_yard_share_transform(df):
    year = df['game_id'].str.split('_').str[0].max()
    week = df['week'].max()
    names = df[['receiver_id', 'receiver']].drop_duplicates().dropna()
    my_cols = ['receiver_id', 'posteam', 'play_type', 'air_yards']
    play_type = df['play_type'] == 'pass'
    df =  df.loc[play_type, my_cols].copy()
    df = (df.groupby(['receiver_id', 'posteam'])
            .agg(targets=('play_type', 'count'), air_yards=('air_yards', 'sum'))
            .sort_values('targets', ascending=False)
            )
    df = (df.assign(team_targets=df.groupby('posteam')['targets'].transform('sum'))
           .assign(team_air_yards=df.groupby('posteam')['air_yards'].transform('sum'))
         )
    df = (df.assign(target_share=df['targets'] / df['team_targets'])
            .assign(air_yard_share= df['air_yards'] / df['team_air_yards'])
            .assign(year=year)
            .assign(week=week)
            .reset_index()
            .merge(names, how='left', on='receiver_id')
            .drop(columns='receiver_id')
            .set_index('receiver')
         )
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
    df = df.copy()
    names = df[['rusher_id', 'rusher']].drop_duplicates().dropna()
    year = df['game_id'].str.split('_').str[0].max()
    week = df['week'].max()
    inside_5 = df.loc[(df['yardline_100']<5) &
             (df['play_type']=='run')]
    carries_5 = (
    inside_5.groupby(['rusher_id', 'posteam'])[['play_id']]
    .count()
    .reset_index()
    .sort_values(by=['play_id'],ascending=False)
    .reset_index(drop=True)
    )
    carries_5 = (carries_5.assign(year=year)
                          .assign(week=week)
    )
    carries_5 = carries_5.merge(names, on='rusher_id').drop(columns=['rusher_id']).set_index('rusher')
    return carries_5

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
    df = df.copy()
    names = df[['receiver_id', 'receiver']].drop_duplicates().dropna().set_index('receiver_id')
    year = df['game_id'].str.split('_').str[0].max()
    week = df['week'].max() 
    df_cols = ['receiver_id', 'posteam', 'air_yards']
    play_type = df['play_type'] == 'pass'
    air_yard_threshold = ~df['air_yards'].isna()
    df = df.loc[play_type & air_yard_threshold, df_cols]
    df['total_air_yards'] = df.groupby(['receiver_id', 'posteam'])['air_yards'].transform('sum')
    df = df.sort_values(['total_air_yards', 'receiver_id', 'posteam'], ascending=False).drop(columns='total_air_yards').reset_index(drop=True)
    df['colors'] = df['posteam'].map(nfl_color_map)
    df['logo'] = df['posteam'].map(nfl_logo_espn_path_map)
    df = (df.assign(year=year)
            .assign(week=week)
         )
    df = df.merge(names, how='left', left_on='receiver_id', right_index=True).drop(columns='receiver_id')
    return df

def headshot_url_join(df, *years):
    df = df.copy()
    player_df = get_nfl_fast_r_roster_data(years)
    player_df = player_df.loc[player_df['teamPlayers.positionGroup'].isin(['WR', 'RB', 'TE'])].copy()
    player_df['abbrev_name'] = player_df['teamPlayers.firstName'].str[0] + '.' + player_df['teamPlayers.lastName']
    player_df = player_df[['abbrev_name','team.abbr', 'teamPlayers.headshot_url']]
    df = pd.merge(df, player_df, left_on=['posteam', 'receiver'], right_on=['team.abbr', 'abbrev_name'], how='left')
    #df = df.fillna({'teamPlayers.headshot_url': nfl_logo_espn_path_map['NFL']})
    df.drop(columns=['abbrev_name', 'team.abbr'])
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
        
        #headshot logo
        else:        
            headshot_url = selection['teamPlayers.headshot_url'].max()
            if pd.isna(headshot_url):
                hs_path = nfl_logo_espn_path_map['NFL']
                hs_image = OffsetImage(plt.imread(hs_path), zoom=.5)
                ax.add_artist(AnnotationBbox(hs_image, xy=(0.1,0.9), frameon=False, xycoords='axes fraction'))
            else:
                response = requests.get(headshot_url)
                hs_image_bytes = plt.imread(BytesIO(response.content))
                hs_image = OffsetImage(hs_image_bytes, zoom=.5)
                ax.add_artist(AnnotationBbox(hs_image, xy=(0.1,0.9), frameon=False, xycoords='axes fraction'))
     
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
    
def transform_edsr_total_1d(df):
    """
    Calculates the early down success rate and the total number of first downs for each NFL team 
    
    Early Down Success Rate (EDSR) is the percentage of first downs gained before reaching third down. 
    It's basically an efficiency metric tracking the gaining of a first down on first or second down.
    """
    df = df.copy()
    year = df['game_id'].str.split('_').str[0].max()
    week = df['week'].max()
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

def usage_yardline_breakdown_transform(df, player_type='receiver', play_type='pass'):
    """player_type: rusher, passer, receiver"""
    year = df['game_id'].str.split('_').str[0].max()
    week = df['week'].max()
    player_id = player_type+'_id'
    if isinstance(play_type, str):
        play_type_list = [play_type]
    else: 
        play_type_list = play_type
    df = df.loc[df['play_type'].isin(play_type_list)].copy()
    #create bins
    yardline_labels = ['1 - 20 yardline', '21 - 40 yardline', '41 - 60 yardline', '61 - 80 yardline', '81 - 100 yardline']
    cut_bins = [-1, 20, 40, 60, 80, 100]
    df = df.assign(yardline_100_bin = pd.cut(df['yardline_100'], bins=cut_bins, labels=yardline_labels))
    
    grouped_df_count = df.groupby([player_id, 'yardline_100_bin']).agg(total_count=('yardline_100_bin', 'count'))
    grouped_df_total = df.groupby([player_id]).agg(total_count=('yardline_100_bin', 'count'))
    grouped_df = grouped_df_count.div(grouped_df_total, level=player_id) * 100
    sort = df.groupby(player_id)['play_id'].agg(play_count=('play_id', 'count'))
    grouped_df = (grouped_df.merge(sort, left_index=True, right_index=True)
                            .sort_values('play_count', ascending=False)
                            .drop(columns='play_count')
                 )
    grouped_df = (grouped_df.unstack(level=1).droplevel(0, axis='columns')
                            .reindex(grouped_df.index.get_level_values(0).unique())
                 )
    #bring in player names
    grouped_df.columns = pd.Index(list(grouped_df.columns))
    names = df[[player_id, player_type]].drop_duplicates().dropna().set_index(player_id)
    grouped_df = (grouped_df.merge(names, how='left', left_index=True, right_index=True)
                           .set_index(player_type, drop=True)
        )
    #add year, week and change index to non-categorical
    grouped_df.columns = pd.Index(list(grouped_df.columns))
    grouped_df = (grouped_df.assign(year=year)
                           .assign(week=week)
                 )
                
    return grouped_df


def make_stacked_bar_viz(df, x_size=15, y_size=20, n=25, save=True):
    colors = ['#bc0000', '#808080', '#a9a9a9', '#c0c0c0', '#d3d3d3']
    year = df['year'].max()
    week = df['week'].max()
    player_type = df.index.name.title()
    df = df.drop(columns=['year', 'week']).head(n).copy()
    
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