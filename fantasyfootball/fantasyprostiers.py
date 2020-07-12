# fantasyprostiers.py

import pandas as pd
from os import path
from fantasyfootball.config import FIGURE_DIR
from datetime import date
import sys
import fantasyfootball.config as config
import fantasyfootball.ffcalculator as ffcalculator
import fantasyfootball.fantasypros as fp
from matplotlib import pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import matplotlib.style as style
from sklearn.mixture import GaussianMixture
import numpy as np
from sklearn.cluster import KMeans

def fantasy_pros_ecr_draft_spread_chart(league_dict=config.sean, player_n=50, x_size=20, y_size=15):
    """Produces scatterplot with ranking variances by position """
    today = date.today()
    date_str = today.strftime('%m.%d.%Y')
    df = fp.fantasy_pros_ecr_scrape(league_dict)
    cleaned_df = fp.fantasy_pros_ecr_scrape_column_clean(df)
    ecr = fp.fantasy_pros_ecr_column_reindex(cleaned_df)
    ecr = ecr[:player_n]
    style.use('ggplot')
    fig, ax = plt.subplots()
    colors = {
        'RB': 'red',
        'WR': 'blue',
        'QB': 'green',
        'TE': 'orange',
        'DST' : 'magenta',
        'K' : 'cyan'
    }
    for _, row in ecr.iterrows():
        xmin = row['best']
        xmax = row['worst']
        ymin, ymax = row['rank'], row['rank']
        center = row['avg']
        pos = row['pos']
        player = row['player_name']

        plt.scatter(center, ymax, color='gray', zorder=2, s=100)
        plt.scatter(xmin, ymax, s=1.5, marker= "|", color=colors.get(pos, 'yellow'), alpha=0.5, zorder=1)
        plt.scatter(xmax, ymax, s=1.5, marker= "|", color=colors.get(pos, 'yellow'), alpha=0.5, zorder=1)
        plt.plot((xmin, xmax), (ymin, ymax), colors.get(pos, 'yellow'), alpha=0.5, zorder=1, linewidth=5.0)
        plt.annotate(player, xy=(xmax+1, ymax))

    patches = [mpatches.Patch(color=v, label=k, alpha=0.5) for k, v in colors.items()]
    plt.legend(handles=patches)

    plt.title(f'{date_str} Fantasy Football Draft')
    plt.xlabel('Average Expert Rank')
    plt.ylabel('Expert Consensus Rank')

    fig.set_size_inches(x_size, y_size)
    plt.gca().invert_yaxis()
    plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings.png'))
    return plt.show()

def fantasy_pros_ecr_tier_add(df, player_n=50, cluster_n=8, random_st=7):
    """Adds overall tiers using GuassianMixture model to ECR data """
    df = df.copy()
    df = df.head(player_n)
    gm = GaussianMixture(n_components=cluster_n, random_state=random_st)
    gm.fit(df[['avg']])
    cluster = gm.predict(df[['avg']])
    df['cluster'] = cluster
    df['avg_cluster'] = df['rank'].groupby(df['cluster']).transform('mean')
    df['cluster_rank'] = df['avg_cluster'].transform('rank', method='dense')
    df['cluster_rank'] = df['cluster_rank'].astype('int')
    df.drop(columns=['avg_cluster'], inplace=True)
    return df

def fantasy_pros_ecr_pos_tier_add(df, player_n=50, cluster_n=8, random_st=7):
    """Adds position specific tiers using GuassianMixture model to ECR data """
    df = df.copy()
    df_list = []
    pos_list = ['QB', 'RB', 'WR', 'TE', 'DST', 'K']
    for pos in pos_list:
        pos_df = df.loc[df['pos']==pos]
        pos_df = pos_df.head(player_n)
        gm = GaussianMixture(n_components=cluster_n, random_state=random_st)
        gm.fit(pos_df[['avg']])
        cluster = gm.predict(pos_df[['avg']])
        pos_df['cluster'] = cluster
        pos_df['avg_cluster'] = pos_df['rank'].groupby(pos_df['cluster']).transform('mean')
        pos_df['pos_cluster_rank'] = pos_df['avg_cluster'].transform('rank', method='dense')
        pos_df['pos_cluster_rank'] = pos_df['pos_cluster_rank'].astype('int')
        pos_df.drop(columns=['avg_cluster', 'cluster'], inplace=True)
        df_list.append(pos_df)
    df = pd.concat(df_list)
    df.sort_values('avg', inplace=True)
    df.reset_index(inplace=True, drop=True)
    return df

def fantasy_pros_ecr_draft_spread_chart_with_tiers(league_dict=config.sean, player_n=50, x_size=20, y_size=15):
    """Produces scatterplot with ranking variances and tiers"""
    today = date.today()
    date_str = today.strftime('%m.%d.%Y')
    df = fp.fantasy_pros_ecr_scrape(league_dict)
    cleaned_df = fp.fantasy_pros_ecr_scrape_column_clean(df)
    ecr = fp.fantasy_pros_ecr_column_reindex(cleaned_df)
    ecr = fantasy_pros_ecr_tier_add(ecr, player_n=player_n)
    style.use('ggplot')
    fig, ax = plt.subplots()
    colors = {
        1: 'red',
        2: 'blue',
        3: 'green',
        4: 'orange',
        5: 'magenta',
        6: 'cyan',
        7: '#FFC300',
        8: '#581845'
    }
    for _, row in ecr.iterrows():
        xmin = row['best']
        xmax = row['worst']
        ymin, ymax = row['rank'], row['rank']
        center = row['avg']
        player = row['player_name']
        cluster = row['cluster_rank']
        
        plt.scatter(center, ymax, color='gray', zorder=2, s=100)
        plt.scatter(xmin, ymax, marker= "|", color=colors.get(cluster, 'yellow'), alpha=0.5, zorder=1)
        plt.scatter(xmax, ymax, marker= "|", color=colors.get(cluster, 'yellow'), alpha=0.5, zorder=1)
        plt.plot((xmin, xmax), (ymin, ymax), color=colors.get(cluster, 'yellow'), alpha=0.5, zorder=1, linewidth=5.0)
        plt.annotate(player, xy=(xmax+1, ymax))
    
    patches = [mpatches.Patch(color=v, label='Tier '+str(k), alpha=0.5) for k, v in colors.items()]
    plt.legend(handles=patches)

    plt.title(f'{date_str} Fantasy Football Draft')
    plt.xlabel('Average Expert Rank')
    plt.ylabel('Expert Consensus Rank')

    plt.gca().invert_yaxis()
    fig.set_size_inches(x_size, y_size)
    plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings_tiers.png'))
    return plt.show()

def fantasy_pros_ecr_draft_spread_chart_with_tiers_by_pos(league_dict=config.sean, player_n=50, x_size=20, y_size=15):
    """Produces scatterplot with ranking variances by position and tiers"""
    today = date.today()
    date_str = today.strftime('%m.%d.%Y')
    pos_list = ['QB', 'RB', 'WR', 'TE', 'DST', 'K']
    df = fp.fantasy_pros_ecr_scrape(league_dict)
    cleaned_df = fp.fantasy_pros_ecr_scrape_column_clean(df)
    ecr = fp.fantasy_pros_ecr_column_reindex(cleaned_df)
    ecr = fantasy_pros_ecr_pos_tier_add(ecr, player_n=player_n)
    ecr['pos_rank'].replace('[^0-9]', '', regex=True, inplace=True)
    ecr['pos_rank'] = ecr['pos_rank'].astype('int')
    style.use('ggplot')
    for pos in pos_list:
        ecr_pos = ecr.copy()
        ecr_pos = ecr_pos.loc[ecr_pos['pos']==pos]
        fig, ax = plt.subplots()
        colors = {
            1: 'red',
            2: 'blue',
            3: 'green',
            4: 'orange',
            5: '#900C3F', #purple
            6: '#2980B9', #blue-green
            7: '#FFC300', #gold
            8: '#581845' #dark purple
        }
        for _, row in ecr_pos.iterrows():
            xmin = row['best']
            xmax = row['worst']
            ymin, ymax = row['pos_rank'], row['pos_rank']
            center = row['avg']
            player = row['player_name']
            cluster = row['pos_cluster_rank']
            
            plt.scatter(center, ymax, color='gray', zorder=2, s=100)
            plt.scatter(xmin, ymax, marker= "|", color=colors.get(cluster, 'yellow'), alpha=0.5, zorder=1)
            plt.scatter(xmax, ymax, marker= "|", color=colors.get(cluster, 'yellow'), alpha=0.5, zorder=1)
            plt.plot((xmin, xmax), (ymin, ymax), color=colors.get(cluster, 'yellow'), alpha=0.5, zorder=1, linewidth=5.0)
            plt.annotate(player, xy=(xmax+1, ymax))
        
        patches = [mpatches.Patch(color=v, label='Tier '+str(k), alpha=0.5) for k, v in colors.items()]
        plt.legend(handles=patches)

        plt.title(f'{date_str} Fantasy Football Draft - {pos}')
        plt.xlabel('Average Expert Overall Rank')
        plt.ylabel('Expert Consensus Position Rank')

        plt.gca().invert_yaxis()
        fig.set_size_inches(x_size, y_size)
        plt.savefig(path.join(FIGURE_DIR,fr'{date_str}_rangeofrankings_tiers_{pos}.png'))
    return plt.show()

def cluster_component_silhouette_estimator(df, df_col='avg', x_size=15, y_size=10):
    """Plots the Akaike's Information Criterion (AIC) and Bayesian Information Criterion (BIC) for clusters in a range for a dataset
    The goal is to pick the number of clusters that minimize the AIC or BIC
     """
    n_components = np.arange(1, 21)
    models = [GaussianMixture(n_components=n, covariance_type='full', random_state=7).fit(df[[df_col]])
            for n in n_components]

    fig, ax = plt.subplots()
    plt.plot(n_components, [m.bic(df[[df_col]]) for m in models], label='BIC')
    plt.plot(n_components, [m.aic(df[[df_col]]) for m in models], label='AIC')
    plt.legend(loc='best')
    plt.xlabel('n_components')                                                               
    fig.set_size_inches(x_size, y_size)
    return plt.show()

def cluster_component_silhouette_estimator_2D(df, df_col_list=['avg', 'rank'], x_size=15, y_size=10):
    """Plots the Akaike's Information Criterion (AIC) and Bayesian Information Criterion (BIC) for clusters in a range for a dataset
    The goal is to pick the number of clusters that minimize the AIC or BIC
     """
    n_components = np.arange(1, 21)
    models = [GaussianMixture(n_components=n, covariance_type='full', random_state=7).fit(df[df_col_list])
            for n in n_components]

    fig, ax = plt.subplots()
    plt.plot(n_components, [m.bic(df[df_col_list]) for m in models], label='BIC')
    plt.plot(n_components, [m.aic(df[df_col_list]) for m in models], label='AIC')
    plt.legend(loc='best')
    plt.xlabel('n_components')                                                               
    fig.set_size_inches(x_size, y_size)
    return plt.show()

def cluster_component_elbow_estimator(df, df_col, x_size=15, y_size=10):
    """Plots distorition for a given cluster # - the optimal cluster # will be the point in which the line flattens out, forming an elbow """
    distortions = []
    K = range(1,21)
    for k in K:
        kmeanModel = KMeans(n_clusters=k)
        kmeanModel.fit(df[[df_col]])
        distortions.append(kmeanModel.inertia_)
    fig, ax = plt.subplots()
    plt.plot(K, distortions, 'bx-')
    plt.xlabel('k')
    plt.ylabel('Distortion')
    plt.title('The Elbow Method showing the optimal k')
    fig.set_size_inches(x_size, y_size)
    return plt.show()

if __name__ == "__main__":
    fantasy_pros_ecr_draft_spread_chart_with_tiers_by_pos()