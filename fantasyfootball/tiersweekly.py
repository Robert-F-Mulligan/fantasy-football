#tiersweekly.py

from fantasyfootball import tiers
from fantasyfootball import fantasypros as fp
from fantasyfootball import config
from fantasyfootball import ffcalculator
from fantasyfootball.config import FIGURE_DIR
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from matplotlib import pyplot as plt
from matplotlib import patches as mpatches
from matplotlib.lines import Line2D
import numpy as np
import matplotlib.style as style
from datetime import date
from os import path
from collections import OrderedDict


def make_clustering_viz_flex(tiers=15, kmeans=False, league=config.sean, player_cutoff=150, player_per_chart=50, x_size=20, y_size=15, covariance_type='diag', save=True, export=False, player_list=None):
    """
    Generates a chart with colored tiers; you can either use kmeans of GMM
    Optional: Pass in a custom tier dict to show varying numbers of tiers; default will be uniform across position
    Optional: Pass in a custom pos_n dict to show different numbers of players by position
    """
    pos = 'FLEX'
    palette = ['red', 'blue', 'green', 'orange', '#900C3F', 'maroon', 'cornflowerblue', 'greenyellow', 'coral', 'orchid', 'firebrick', 'lightsteelblue', 'palegreen', 'darkorange', 'crimson', 'darkred', 'aqua', 'forestgreen', 'navajowhite', 'mediumpurple']
    pos_shape = {
        'RB': 'o',
        'WR': 's',
        'TE': '^'
        }
    df = fp.fantasy_pros_ecr_weekly_scrape(league)
    #derive pos for flex players
    pos_df = df.loc[df['pos'] != pos]
    pos_map = dict(zip(pos_df['player_name'].to_list(), pos_df['pos'].to_list()))
    df['pos_map'] = df['player_name'].map(pos_map)
    df = (df.loc[df['pos'] == pos]
        .sort_values('rank')
        .reset_index(drop=True)
        .head(player_cutoff)
    )
    df['pos_rank'] = (df['pos_rank'].replace('[^0-9]', '', regex=True)
                                    .astype('int')
                     )
    today = date.today()
    date_str = today.strftime('%m.%d.%Y')
    x = df.loc[:, ['best', 'worst', 'avg']].copy()
    if kmeans:
        kmm = KMeans(n_clusters=tiers).fit(x)
        labels = kmm.predict(x)
    else: #gausianmixture
        gmm = GaussianMixture(n_components=tiers, covariance_type=covariance_type, random_state=0).fit(x)
        labels = gmm.predict(x)
    unique_labels = list(OrderedDict.fromkeys(labels))
    rank_dict = dict(zip(unique_labels, range(1,len(unique_labels)+1)))
    df['tiers'] = labels
    df['tiers'] = df['tiers'].map(rank_dict)                             
    
    style.use('ggplot')
    colors = dict(zip(range(1, tiers+1), palette[:tiers]))
    tier_lookup = dict(zip(palette[:tiers], range(1, tiers+1)))

    chart_n = (player_cutoff // player_per_chart) + (player_cutoff % player_per_chart > 0)
    #filter current team players
    if isinstance(player_list, list):
        df = df.loc[df['player_name'].isin(player_list)].copy()
    
    for ix, chunk_df in enumerate(np.array_split(df, chart_n)):
        fig, ax = plt.subplots();
        min_tier = min(chunk_df['tiers'])
        max_tier = max(chunk_df['tiers'])
        patches = []
        color_chunk = [colors[i] for i in range(min_tier, max_tier + 1)]
        patches = [mpatches.Patch(color=color, alpha=0.5, label=f'Tier {tier_lookup[color]}') for color in color_chunk]
        pos_patches = [Line2D([0], [0], color='gray', label=pos, marker=shape, lw=0, markersize=12) for pos, shape in pos_shape.items()]
        
        for _, row in chunk_df.iterrows():
            xmin = row['best']
            xmax = row['worst']
            ymin, ymax = row['pos_rank'], row['pos_rank']
            center = row['avg']
            player = row['player_name'] + ', ' +row['tm'] + ' (' + row['pos_map'] + ')'
            tier = row['tiers']
            
            plt.scatter(center, ymax, color='gray', zorder=2, s=100, marker=pos_shape[row['pos_map']])
            plt.scatter(xmin, ymax, marker= "|", color=colors.get(tier, 'moccasin'), alpha=0.5, zorder=1)
            plt.scatter(xmax, ymax, marker= "|", color=colors.get(tier, 'moccasin'), alpha=0.5, zorder=1)
            plt.plot((xmin, xmax), (ymin, ymax), color=colors.get(tier, 'moccasin'), alpha=0.5, zorder=1, linewidth=5.0)
            plt.annotate(player, xy=(xmax+1, ymax))

        #first legend
        first_legend = plt.legend(handles=pos_patches, loc='lower left', borderpad=1, fontsize=12)
        ax = plt.gca().add_artist(first_legend)
        #second legend
        plt.legend(handles=patches, borderpad=1, fontsize=12)
        if player_list is  not None:
            league_name = league['name']
            plt.title(f'{date_str} Fantasy Football Weekly - {pos} - {league_name} - {ix+1}')
        else:
            plt.title(f'{date_str} Fantasy Football Weekly - {pos} {ix+1}')
        plt.xlabel('Average Expert Overall Rank')
        plt.ylabel('Expert Consensus Position Rank')

        fig.set_size_inches(x_size, y_size)
        plt.gca().invert_yaxis()
        #plt.tight_layout()
        if save:
            if kmeans:
                if player_list is not None:
                    plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings_kmeans__FLEX_{league_name}_{ix+1}.png'))
                else: 
                    plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings_kmeans__{pos}_{ix+1}.png'))
            else:
                if player_list is not None:
                    plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings_gmm__FLEX_list{league_name}_{ix+1}.png'))
                else:
                    plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings_gmm_{pos}_{ix+1}.png'))
        if export:
            df.to_csv(path.join(FIGURE_DIR,fr'{date_str}_ecr_tiers.csv'), index=False)              
    return plt.show()

if __name__ == "__main__":
    #run elbow chart or AIC/BIC chart to estimate optimal number of k for each pos
    #revisit week 1 to see if URL changes for each week - if so, refactor viz func and fp df func

    sean = config.sean
    work = config.work
    justin = config.justin
    
    pos_tier_dict_viz = {
    'RB' : 8,
    'QB' : 6,
    'WR' : 5,
    'TE' : 5,
    'DST' : 6,
    'K' : 7
    }

    flex_list = [
        'Clyde Edwards-Helaire',
        'Allen Robinson II',
        'Adam Thielen',
        'Robert Woods',
        'Austin Ekeler',
        'Joe Mixon',
        'Terry McLaurin',
        'Todd Gurley II',
        'Chris Carson',
        'Stefon Diggs',
        'Miles Sanders',
        'Diontae Johnson',
        'Jarvis Landry',
        'CeeDee Lamb',
        'Melvin Gordon III',
        'John Brown',
        'Hunter Henry',
        'Mark Ingram II',
        'James White',
        'Hayden Hurst',
        'Sammy Watkins',
        'Tarik Cohen',
        'Christian Kirk',
        'Chris Herndon IV',
        'Leonard Fournette',
        'Boston Scott',
        'Frank Gore',
        'Chris Thompson',
        'Michael Thomas',
        'George Kittle',
        'Jack Doyle']

    work_list = [
        'Robert Woods',
        'CeeDee Lamb',
        'Chris Carson',
        'Hunter Henry',
        'Stefon Diggs',
        'Austin Ekeler',
        'Joe Mixon',
        'Todd Gurley II',
        'John Brown',
        'Miles Sanders',
        'Hayden Hurst',
        'Chris Herndon IV',
        'Leonard Fournette',
        'Boston Scott',
        'Michael Thomas',
        ]

    sean_list = [
        'Adam Thielen',
        'Robert Woods',
        'Joe Mixon',
        'Todd Gurley II',
        'Jarvis Landry',
        'Melvin Gordon III',
        'Tarik Cohen',
        'Christian Kirk',
        'Chris Herndon IV',
        'Chris Thompson',
        'George Kittle'
        ]

    justin_list = [
        'Clyde Edwards-Helaire',
        'Allen Robinson II',
        'Robert Woods',
        'Austin Ekeler',
        'Terry McLaurin',
        'Diontae Johnson',
        'Hunter Henry',
        'Mark Ingram II',
        'James White',
        'Sammy Watkins',
        'Frank Gore',
        'Jack Doyle',
        'Denzel Mims'
        ]

    #tiers.make_clustering_viz(tier_dict=pos_tier_dict_viz, league=league, pos_n=35, covariance_type='diag', draft=False, save=False)
    #make_clustering_viz_flex(export=True)
    make_clustering_viz_flex(tiers=5, league=sean, player_list=sean_list)
    make_clustering_viz_flex(tiers=5, league=work, player_list=work_list)
    make_clustering_viz_flex(tiers=5, league=justin, player_list=justin_list)
