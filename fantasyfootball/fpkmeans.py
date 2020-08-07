# fantasyprostierskmeans.py

from sklearn.cluster import KMeans 
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from matplotlib import patches as mpatches
import numpy as np
from mpl_toolkits import mplot3d
from fantasyfootball import fantasypros as fp
import matplotlib.style as style
from datetime import date
from fantasyfootball import config
from fantasyfootball.config import FIGURE_DIR
from os import path

league = config.sean

#run SSE chart to pick cluster #s
pos_elbow = {
    'RB' : 5,
    'QB' : 4,
    'WR' : 5,
    'TE' : 4,
    'DST' : 3,
    'K' : 3
    }

total_elbow = {
    'RB' : 6,
    'QB' : 4,
    'WR' : 6,
    'TE' : 6,
    'DST' : 4,
    'K' : 4
    }


def kmeans_sse_chart_pos_cutoff(league, n=35):
    df = fp.fantasy_pros_ecr_process(league)
    fig, ax = plt.subplots(2, 3); fig.set_size_inches(15, 10)
    pos = {
        'RB': ax[0][0], # top left
        'WR': ax[0][1], # top middle
        'QB': ax[1][0], # bottom left
        'TE': ax[1][1],  # bottom middle
        'DST': ax[0][2], # top right
        'K': ax[1][2] # bottom right
        }
    for p, ax in pos.items():
        pos_df = df.loc[df['pos'] == p].head(n).copy()
        x = pos_df[['avg' ,'best', 'worst']].values
        sse = {}
        for k in range(1, 20):
            kmm = KMeans(n_clusters=k).fit(x)
            sse[k] = kmm.inertia_ # within-cluster-sum-of-squares

        ax.plot(list(sse.keys()), list(sse.values()))
        ax.set_xlabel("Number of clusters")
        ax.set_ylabel("SSE")
        ax.set_xticks(np.arange(1, 20, step=1))
        ax.set_title(p)   
    #plt.tight_layout()
    return plt.show()

def kmeans_sse_chart_total_cutoff(league=config.sean):
    df = fp.fantasy_pros_ecr_process(league)
    fig, ax = plt.subplots(2, 3); fig.set_size_inches(15, 10)
    pos = {
        'RB': ax[0][0], # top left
        'WR': ax[0][1], # top middle
        'QB': ax[1][0], # bottom left
        'TE': ax[1][1],  # bottom middle
        'DST': ax[0][2], # top right
        'K': ax[1][2] # bottom right
        }
    for p, ax in pos.items():
        pos_df = df.loc[df['pos'] == p].copy()
        x = pos_df[['avg' ,'best', 'worst']].values
        sse = {}
        for k in range(1, 20):
            kmm = KMeans(n_clusters=k).fit(x)
            sse[k] = kmm.inertia_ # within-cluster-sum-of-squares

        ax.plot(list(sse.keys()), list(sse.values()))
        ax.set_xlabel("Number of clusters")
        ax.set_ylabel("SSE")
        ax.set_xticks(np.arange(1, 20, step=1))
        ax.set_title(p)   
    #plt.tight_layout()
    return plt.show()

def make_clustering_viz(elbow, league=config.sean, n=35, x_size=20, y_size=15):
    df = fp.fantasy_pros_ecr_process(league)
    df['pos_rank'].replace('[^0-9]', '', regex=True, inplace=True)
    df['pos_rank'] = df['pos_rank'].astype('int')
    today = date.today()
    date_str = today.strftime('%m.%d.%Y')
    for p, k in elbow.items():
        pos_df = df.loc[df['pos'] == p].head(n).copy().reset_index(drop=True)
        x = pos_df.loc[:, ['best', 'worst', 'avg']].copy().head(n).reset_index(drop=True)
        kmm = KMeans(n_clusters=k).fit(x)
        labels = kmm.predict(x)
        unique_labels = []
        tiers = []
        for i in labels:
            if i not in unique_labels:
                unique_labels.append(i)
            tiers.append(len(set(unique_labels)))
        
        pos_df['pos_tiers'] = tiers                              
        style.use('ggplot')
        colors = ['red', 'blue', 'green', 'orange', '#900C3F', '#2980B9', '#FFC300', '581845']
        colors = dict(zip(range(1, k+1), colors[:k]))

        fig, ax = plt.subplots(); fig.set_size_inches(8,10);
        for _, row in pos_df.iterrows():
            xmin = row['best']
            xmax = row['worst']
            ymin, ymax = row['pos_rank'], row['pos_rank']
            center = row['avg']
            player = row['player_name']
            tier = row['pos_tiers']
            
            plt.scatter(center, ymax, color='gray', zorder=2, s=100)
            plt.scatter(xmin, ymax, marker= "|", color=colors.get(tier, 'yellow'), alpha=0.5, zorder=1)
            plt.scatter(xmax, ymax, marker= "|", color=colors.get(tier, 'yellow'), alpha=0.5, zorder=1)
            plt.plot((xmin, xmax), (ymin, ymax), color=colors.get(tier, 'yellow'), alpha=0.5, zorder=1, linewidth=5.0)
            plt.annotate(player, xy=(xmax+1, ymax))

        patches = []
        for tier, color in colors.items():
            patch = mpatches.Patch(color=color, alpha=0.5, label=f'Tier {tier}')
            patches.append(patch)

        plt.legend(handles=patches, borderpad=1, fontsize=12)
        plt.title(f'{date_str} Fantasy Football Draft - {p}')
        plt.xlabel('Average Expert Overall Rank')
        plt.ylabel('Expert Consensus Position Rank')

        plt.gca().invert_yaxis()
        fig.set_size_inches(x_size, y_size)
        plt.tight_layout()
        plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings_kmeans.png'))
    return plt.show()

def assign_k_means_pos_cutoff_cluster(df ,elbow, n=35):
    df_list = []
    for p, k in elbow.items():
        pos_df = df.loc[df['pos'] == p].head(n).copy().reset_index(drop=True)
        x = pos_df.loc[:, ['best', 'worst', 'avg']].copy().head(n).reset_index(drop=True)
        kmm = KMeans(n_clusters=k).fit(x)
        labels = kmm.predict(x)
        unique_labels = []
        tiers = []
        for i in labels:
            if i not in unique_labels:
                unique_labels.append(i)
            tiers.append(len(set(unique_labels)))
        pos_df['pos_tiers'] = tiers
        df_list.append(pos_df)
    df = pd.concat(df_list, ignore_index=True)
    df.sort_values('rank', inplace=True)
    df.reset_index(inplace=True, drop=True)
    return df

def assign_k_means_total_cutoff_cluster(df ,elbow):
    df_list = []
    df = df.copy()
    for p, k in elbow.items():
        pos_df = df.loc[df['pos'] == p].copy().reset_index(drop=True)
        x = pos_df.loc[:, ['best', 'worst', 'avg']].copy().reset_index(drop=True)
        kmm = KMeans(n_clusters=k).fit(x)
        labels = kmm.predict(x)
        unique_labels = []
        tiers = []
        for i in labels:
            if i not in unique_labels:
                unique_labels.append(i)
            tiers.append(len(set(unique_labels)))
        pos_df['pos_tiers'] = tiers
        df_list.append(pos_df)
    df = pd.concat(df_list, ignore_index=True)
    df.sort_values('rank', inplace=True)
    df.reset_index(inplace=True, drop=True)
    return df

if __name__ == "__main__":
    make_clustering_viz(elbow=pos_elbow, league=league)