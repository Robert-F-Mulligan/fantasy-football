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
import numpy as np
import matplotlib.style as style
from datetime import date
from os import path


def make_clustering_viz_flex(tiers=20, kmeans=False, league=config.sean, player_cutoff=250, player_per_chart=50, x_size=20, y_size=15, covariance_type='diag', save=True):
    """
    Generates a chart with colored tiers; you can either use kmeans of GMM
    Optional: Pass in a custom tier dict to show varying numbers of tiers; default will be uniform across position
    Optional: Pass in a custom pos_n dict to show different numbers of players by position
    """
    pos = 'FLEX'
    palette = ['red', 'blue', 'green', 'orange', '#900C3F', 'maroon', 'cornflowerblue', 'greenyellow', 'coral', 'orchid', 'firebrick', 'lightsteelblue', 'palegreen', 'darkorange', 'crimson', 'darkred', 'aqua', 'forestgreen', 'navajowhite', 'mediumpurple']
    df = fp.fantasy_pros_ecr_weekly_scrape(league)
    #derive pos for players
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
    unique_labels = []
    for i in labels:
        if i not in unique_labels:
            unique_labels.append(i)
    rank_dict = dict(zip(unique_labels, range(1,len(unique_labels)+1)))
    df['tiers'] = labels
    df['tiers'] = df['tiers'].map(rank_dict)                             
    
    style.use('ggplot')
    colors = dict(zip(range(1, tiers+1), palette[:tiers]))
    tier_lookup = dict(zip(palette[:tiers], range(1, tiers+1)))

    chart_n = (player_cutoff // player_per_chart) + (player_cutoff % player_per_chart > 0)

    for ix, chunk_df in enumerate(np.array_split(df, chart_n)):
        fig, ax = plt.subplots();
        min_tier = min(chunk_df['tiers'])
        max_tier = max(chunk_df['tiers'])
        patches=[]
        color_chunk = [colors[i] for i in range(min_tier, max_tier + 1)]
        for color in color_chunk:
            patch = mpatches.Patch(color=color, alpha=0.5, label=f'Tier {tier_lookup[color]}')
            patches.append(patch)

        for _, row in chunk_df.iterrows():
            xmin = row['best']
            xmax = row['worst']
            ymin, ymax = row['pos_rank'], row['pos_rank']
            center = row['avg']
            player = row['player_name'] + ', ' +row['tm'] + ' (' + row['pos_map'] + ')'
            tier = row['tiers']
            
            plt.scatter(center, ymax, color='gray', zorder=2, s=100)
            plt.scatter(xmin, ymax, marker= "|", color=colors.get(tier, 'moccasin'), alpha=0.5, zorder=1)
            plt.scatter(xmax, ymax, marker= "|", color=colors.get(tier, 'moccasin'), alpha=0.5, zorder=1)
            plt.plot((xmin, xmax), (ymin, ymax), color=colors.get(tier, 'moccasin'), alpha=0.5, zorder=1, linewidth=5.0)
            plt.annotate(player, xy=(xmax+1, ymax))

        plt.legend(handles=patches, borderpad=1, fontsize=12)
        plt.title(f'{date_str} Fantasy Football Weekly - {pos} {ix+1}')
        plt.xlabel('Average Expert Overall Rank')
        plt.ylabel('Expert Consensus Position Rank')

        fig.set_size_inches(x_size, y_size)
        plt.gca().invert_yaxis()
        #plt.tight_layout()
        if save:
            if kmeans:
                plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings_kmeans__{pos}_{ix+1}.png'))
            else:
                plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings_gmm_{pos}_{ix+1}.png'))
            
    return plt.show()

if __name__ == "__main__":
    #run elbow chart or AIC/BIC chart to estimate optimal number of k for each pos
    #revisit week 1 to see if URL changes for each week - if so, refactor viz func and fp df func

    league = config.sean
    
    pos_tier_dict_viz = {
    'RB' : 8,
    'QB' : 6,
    'WR' : 5,
    'TE' : 5,
    'DST' : 6,
    'K' : 7
    }

    #tiers.make_clustering_viz(tier_dict=pos_tier_dict_viz, league=league, pos_n=35, covariance_type='diag', draft=False, save=False)
    make_clustering_viz_flex()