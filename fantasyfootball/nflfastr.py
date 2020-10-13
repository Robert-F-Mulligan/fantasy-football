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
        team_list = [team for team in team_filter]
        df = df.loc[df['posteam'].isin(team_list)].copy()
    else:
        df = df.head(n).copy()
    sns.set_style('whitegrid');
    df['color'] = df['posteam'].map(nfl_color_map)
    fig, ax = plt.subplots(figsize=(x_size, y_size))
    ax.scatter(df['target_share'], df['air_yard_share'], color=df['color'], alpha=1.0)
    text = [ax.annotate(name, xy=(x+.001, y), alpha=1.0, zorder=2) for name, x, y 
        in zip(df['receiver'], df['target_share'], df['air_yard_share'])]
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
        team_list = [team for team in team_filter]
        df = df.loc[df['posteam'].isin(team_list)].copy()
    else:
        df = df.head(n).copy()
    #color and logo mapping
    df['color'] = df['posteam'].map(nfl_color_map)
    df['logo'] = df['posteam'].map(nfl_logo_espn_path_map)
    sns.set_style('whitegrid');
    fig,ax = plt.subplots(figsize=(x_size, y_size))
    ax.barh(df['rusher'], df['play_id'], color=df['color'])
    for carries, x, y in zip(df['play_id'], df['play_id'], df['rusher']):
        ax.annotate(carries, xy=(x, y), fontsize=12)
    images = [OffsetImage(plt.imread(file_path), zoom=.1) for file_path in df['logo'].to_list()]
    x0 = [(df['play_id'].max() * 0.02)] * len(df['play_id'])
    for im, x, y in zip(images, x0, df['rusher']):
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
    year = df['game_id'].str.split('_').str[0].max()
    week = df['week'].max() 
    df_cols = ['receiver', 'posteam', 'air_yards']
    play_type = df['play_type'] == 'pass'
    air_yard_threshold = ~df['air_yards'].isna()
    df = df.loc[play_type & air_yard_threshold, df_cols]
    df['total_air_yards'] = df.groupby(['receiver', 'posteam'])['air_yards'].transform('sum')
    df = df.sort_values(['total_air_yards', 'receiver', 'posteam'], ascending=False).drop(columns='total_air_yards').reset_index(drop=True)
    df['colors'] = df['posteam'].map(nfl_color_map)
    df['logo'] = df['posteam'].map(nfl_logo_espn_path_map)
    df = (df.assign(year=year)
            .assign(week=week)
         )
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
        fig.savefig(path.join(FIGURE_DIR,f'{year}Air_Yard_Density_Through{week}.png'), bbox_inches='tight')