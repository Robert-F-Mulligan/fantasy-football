# fantasyprostierskmeans.py

from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
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
from fantasyfootball import ffcalculator
from os import path
from collections import OrderedDict

#run SSE or AIC/BIC chart to pick cluster #s
pos_tier_dict_viz = {
    'RB' : 8,
    'QB' : 6,
    'WR' : 5,
    'TE' : 5,
    'DST' : 6,
    'K' : 7
    }

#optionally run draftable_position_quantity() func to determine "draftable" number by pos
draftable_quantity_dict = {
    'RB' : 56,
    'QB' : 19,
    'WR' : 57,
    'TE' : 20,
    'DST' : 15,
    'K' : 15
    }

def kmeans_sse_chart(league=config.sean, pos_breakout=True, pos_n=None, clusters=10):
    """
    Plots the SSE for different k-means cluster values for k
    Specify a number for n if you wish to segment position groups by a cutoff number
    Plots distorition for a given cluster # - the optimal cluster # will be the point in which the line flattens out, forming an elbow
    Optional: Pass a dict with specific quanities per posiiton
    """
    df = fp.fantasy_pros_ecr_process(league)
    if pos_breakout:
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
            if pos_n is None:
                pos_df = df.loc[df['pos'] == p].copy()
                x = pos_df[['avg' ,'best', 'worst']].to_numpy()
            else:
                if not isinstance(pos_n, dict):
                    pos_n = {k: int(pos_n) for k,v in pos.items()} 
                pos_df = df.loc[df['pos'] == p].head(pos_n[p]).copy()
                x = pos_df[['avg' ,'best', 'worst']].to_numpy()
            n_components = range(1, clusters+1)
            
            models = [KMeans(n_clusters=n).fit(x) 
                    for n in n_components]

            ax.plot(n_components, [m.inertia_ for m in models], label='SSE')
            ax.set_xlabel("Number of clusters")
            ax.legend(loc='best')
            ax.set_xticks(np.arange(1, clusters+1, step=1))
            ax.set_title(p) 
    else:
        fig, ax = plt.subplots(); fig.set_size_inches(15, 10)
        full_df = df.head(200).copy()
        x = full_df[['avg' ,'best', 'worst']].to_numpy()
        n_components = range(1, clusters+1)
        models = [KMeans(n_clusters=n).fit(x) 
                    for n in n_components]

        ax.plot(n_components, [m.inertia_ for m in models], label='SSE')
        ax.set_xlabel("Number of clusters")
        ax.legend(loc='best')
        ax.set_xticks(np.arange(1, clusters+1, step=1)) 
    return plt.show()

def gmm_component_silhouette_estimator(league=config.sean, pos_breakout=True, pos_n=None, components=10, covariance_type='diag'):
    """
    Plots the Akaike's Information Criterion (AIC) and Bayesian Information Criterion (BIC) for clusters in a range for a dataset
    The goal is to pick the number of clusters that minimize the AIC or BIC
    """
    df = fp.fantasy_pros_ecr_process(league)
    if pos_breakout:
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
            if pos_n is None:
                pos_df = df.loc[df['pos'] == p].copy()
                x = pos_df[['avg' ,'best', 'worst']].to_numpy()
            else:
                if not isinstance(pos_n, dict):
                    pos_n = {k: int(pos_n) for k,v in pos.items()} 
                pos_df = df.loc[df['pos'] == p].head(pos_n[p]).copy()
                x = pos_df[['avg' ,'best', 'worst']].to_numpy()
            n_components = range(1, components+1)
            models = [GaussianMixture(n_components=n, covariance_type=covariance_type, random_state=0).fit(x)
                    for n in n_components]

            ax.plot(n_components, [m.bic(x) for m in models], label='BIC')
            ax.plot(n_components, [m.aic(x) for m in models], label='AIC')
            ax.set_xticks(np.arange(1, components+1, step=1))
            ax.legend(loc='best')
            ax.set_xlabel('n_components')                                                               
            ax.set_title(p)
    else:
        fig, ax = plt.subplots(); fig.set_size_inches(15, 10)
        full_df = df.head(200).copy()
        x = full_df[['avg' ,'best', 'worst']].to_numpy()
        n_components = range(1, components+1)
        models = [GaussianMixture(n_components=n, covariance_type=covariance_type, random_state=0).fit(x)
                for n in n_components]

        ax.plot(n_components, [m.bic(x) for m in models], label='BIC')
        ax.plot(n_components, [m.aic(x) for m in models], label='AIC')
        ax.set_xticks(np.arange(1, components+1, step=1))
        ax.legend(loc='best')
        ax.set_xlabel('n_components')    
    return plt.show()

def make_clustering_viz(tier_dict=8, kmeans=False, league=config.sean, pos_n=35, x_size=20, y_size=15, covariance_type='diag', draft=True, save=True):
    """
    Generates a chart with colored tiers; you can either use kmeans of GMM
    Optional: Pass in a custom tier dict to show varying numbers of tiers; default will be uniform across position
    Optional: Pass in a custom pos_n dict to show different numbers of players by position
    """
    palette = ['red', 'blue', 'green', 'orange', '#900C3F', '#2980B9', '#FFC300', '#581845']
    if draft:
        df = fp.fantasy_pros_ecr_process(league)
    else:
        df = fp.fantasy_pros_ecr_weekly_scrape(league)
    df['pos_rank'] = (df['pos_rank'].replace('[^0-9]', '', regex=True)
                                    .astype('int')
                     )
    today = date.today()
    date_str = today.strftime('%m.%d.%Y')
    if not isinstance(tier_dict, dict):
        tier_dict = {pos: tier_dict for  pos in ['QB', 'RB', 'WR', 'TE', 'DST', 'K']}
    if not isinstance(pos_n, dict):
        pos_n = {k: int(pos_n) for k,v in tier_dict.items()}       
    for p, k in tier_dict.items():
        pos_df = df.loc[df['pos'] == p].head(pos_n[p]).copy().reset_index(drop=True)
        x = pos_df.loc[:, ['best', 'worst', 'avg']].head(pos_n[p]).copy().reset_index(drop=True)
        if kmeans:
            kmm = KMeans(n_clusters=k).fit(x)
            labels = kmm.predict(x)
        else: #gausianmixture
            gmm = GaussianMixture(n_components=k, covariance_type=covariance_type, random_state=0).fit(x)
            labels = gmm.predict(x)
        unique_labels = list(OrderedDict.fromkeys(labels))
        rank_dict = dict(zip(unique_labels, range(1,len(unique_labels)+1)))
        pos_df['pos_tiers'] = labels
        pos_df['pos_tiers'] = pos_df['pos_tiers'].map(rank_dict)                             
        
        style.use('ggplot')
        colors = dict(zip(range(1, k+1), palette[:k]))

        fig, ax = plt.subplots();
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

        patches = [mpatches.Patch(color=color, alpha=0.5, label=f'Tier {tier}') for tier, color in colors.items()]

        plt.legend(handles=patches, borderpad=1, fontsize=12)
        if draft:
            plt.title(f'{date_str} Fantasy Football Draft - {p}')
        else:
            plt.title(f'{date_str} Fantasy Football Weekly - {p}')
        plt.xlabel('Average Expert Overall Rank')
        plt.ylabel('Expert Consensus Position Rank')

        fig.set_size_inches(x_size, y_size)
        plt.gca().invert_yaxis()
        #plt.tight_layout()
        if save:
            if kmeans:
                plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings_kmeans_{p}.png'))
            else:
                plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings_gmm_{p}.png'))
         
    return plt.show()

def assign_tier_to_df(df, tier_dict=8, kmeans=False, pos_n=None, covariance_type='diag'):
    """
    Assigns a tier by position to a dataframe (either kmeans or GMM method)
    Optional: Pass in a custom tier dict to show varying numbers of tiers; default will be uniform across position
    Optional: Pass in a custom pos_n dict to show different numbers of players by position
    """
    df_list = []
    df = df.copy()
    if not isinstance(tier_dict, dict):
        tier_dict = {pos: int(tier_dict) for  pos in ['QB', 'RB', 'WR', 'TE', 'DST', 'K']}
    for p, k in tier_dict.items():
        if pos_n is None:
            pos_df = df.loc[df['pos'] == p].copy()
            extra_df = pd.DataFrame()
            x = pos_df.loc[:, ['best', 'worst', 'avg']].copy().reset_index(drop=True)
        else:
            if not isinstance(pos_n, dict):
                pos_n = {k: int(pos_n) for k,v in tier_dict.items()}
            pos_df = df.loc[df['pos'] == p].head(pos_n[p]).copy().reset_index(drop=True)
            extra_df = df.loc[df['pos'] == p][pos_n[p]:].copy().reset_index(drop=True)
            x = pos_df.loc[:, ['best', 'worst', 'avg']].head(pos_n[p]).copy().reset_index(drop=True)
        if kmeans:
            kmm = KMeans(n_clusters=k).fit(x)
            labels = kmm.predict(x) 
        else:
            gmm = GaussianMixture(n_components=k, covariance_type=covariance_type, random_state=0).fit(x)
            labels = gmm.predict(x)
        unique_labels = []
        for i in labels:
            if i not in unique_labels:
                unique_labels.append(i)
        rank_dict = dict(zip(unique_labels, range(1,len(unique_labels)+1)))
        pos_df['pos_tiers'] = labels
        pos_df['pos_tiers'] = pos_df['pos_tiers'].map(rank_dict)
        extra_df['pos_tiers'] = np.nan
        df_list.append(pos_df)
        df_list.append(extra_df)
    df = pd.concat(df_list, ignore_index=True)
    df = (df.sort_values('rank')
            .reset_index(drop=True)
         )
    return df

def best_worst_avg_3d_viz(league=config.sean, pos_n=35):
    """Grapsh in 3d best, worst and avg by position """
    ecr = fp.fantasy_pros_ecr_process(league)
    pos_list = list(ecr['pos'].unique())
    for pos in pos_list:
        sns.set_style('white')
        fig = plt.figure(); fig.set_size_inches(5, 5)
        ax = plt.axes(projection='3d')
        df = ecr.loc[ecr['pos'] == pos].head(pos_n).copy()
        x, y, z = df['avg'].to_numpy(), df['worst'].to_numpy(), df['best'].to_numpy()
        ax.scatter3D(x, y, z)
        plt.title(f'{pos}')
        plt.show()

def draftable_position_quantity(league=config.sean):
    team_n = league.get('team_n')
    draftable_players = team_n * league.get('rounds')
    pos_values = {'DST': 0, 'K': 0}
    pos_values = {k: team_n for k, v in pos_values.items()} 
    df = ffcalculator.adp_process(league)
    df = df.head(draftable_players)
    pos_list = ['RB', 'WR', 'QB', 'TE']
    for pos in pos_list:
        count = df.loc[df['pos']==pos]['player_name'].count()
        pos_values[pos] = 5 * round(count/5) #round to nearest 5
    return pos_values

if __name__ == "__main__":
    #run elbow chart or AIC/BIC chart to estimate optimal number of k for each pos

    league = config.justin
    
    draftable_pos_dict = draftable_position_quantity(league)

    make_clustering_viz(tier_dict=pos_tier_dict_viz, league=league, pos_n=draftable_pos_dict, covariance_type='diag')