# "fantasypros.py"

import pandas as pd
from bs4 import BeautifulSoup
import requests
from os import path
from datetime import date
import sys
import fantasyfootball.config as config
import fantasyfootball.ffcalculator as ffcalculator
from matplotlib import pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import matplotlib.style as style
from sklearn.mixture import GaussianMixture


def fantasy_pros_scrape(url):
    """Scrape Fantasy Pros stat projections given a URL"""
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    table = soup.find_all('table', attrs={'id':'data'})
    return pd.read_html(str(table))[0]

def fantasy_pros_column_clean(df):
    """Cleans up columns for Fantasy Pros scraped data tables"""
    df = df.copy()
    df.columns = ['_'.join(col) for col in df.columns]
    df.rename(columns={
                'Unnamed: 0_level_0_Player': 'player_name',
                'RUSHING_TDS' : 'rushing_td',
                'RECEIVING_TDS' : 'receiving_td',
                'PASSING_TDS' : 'passing_td',
                'PASSING_INTS' : 'passing_int',
                'MISC_FL' : 'fumbles',
                'MISC_FPTS' : 'ppr_scoring'
                }, inplace=True)
    df.columns = [col.lower() for col in df.columns]
    df['tm'] = df['player_name'].str.split().str[-1]
    df['player_name'] = df['player_name'].str.rsplit(n=1).str[0]
    df['tm'].replace({'JAC' : 'JAX'}, inplace=True)
    return df

def fantasy_pros_column_reindex(df):
    """Adds columns that are missing from Fantasy Pros tables and reorders columns"""
    full_column_list = [
    'id', 'player_name', 'tm', 'pos',
    'receiving_rec', 'receiving_yds', 'receiving_td', 'rushing_att', 'rushing_yds', 'rushing_td', #WR/RB
    'passing_att', 'passing_cmp', 'passing_yds', 'passing_td', 'passing_int', #passing
    'fumbles', 'ppr_scoring'
    ]
    df = df.copy()
    if 'pos' not in df.columns:
        df['pos'] = '-'
    df = df.reindex(columns = full_column_list, fill_value = 0)
    return df

def fantasy_pros_ecr_scrape(league_dict=config.sean):
    """Scrape Fantasy Pros ECR given a league scoring format"""
    scoring = league_dict.get('scoring')
    if scoring == 'ppr':
        url = 'https://www.fantasypros.com/nfl/rankings/ppr-cheatsheets.php'
    elif scoring == 'half-ppr':
        url = 'https://www.fantasypros.com/nfl/rankings/half-point-ppr-cheatsheets.php'
    else:
        url = 'https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php'
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    table = soup.find_all('table')
    return pd.read_html(str(table))[0]

def fantasy_pros_ecr_scrape_column_clean(df):
    df = df.copy()
    df.columns = [col.lower() for col in df.columns]
    df.drop(columns=['wsid'], inplace=True)
    df.dropna(subset=['overall (team)'], inplace=True)
    df['rank'] = df['rank'].astype('int')
    df.rename(columns={
    'overall (team)' : 'player_name',
    'pos' : 'pos_rank'
            }, inplace=True)
    df['tm'] = df['player_name'].str.split().str[-1]
    df['player_name'] = df['player_name'].str.rsplit(n=1).str[0].str.rsplit(n=1).str[0].str[:-2]
    df['pos'] = df['pos_rank']
    df['pos'].replace('\d+', '', regex=True, inplace=True)
    df.reset_index(inplace=True, drop=True)
    return df

def fantasy_pros_ecr_column_reindex(df):
    """Adds columns that are missing from Fantasy Pros tables and reorders columns"""
    full_column_list = [
        'rank', 'player_name', 'pos', 'tm', 'pos_rank', 'bye', 'best', 'worst', 'avg', 'std dev',
       'adp', 'vs. adp' 
       ]
    df = df.copy()
    df = df.reindex(columns = full_column_list, fill_value = 0)
    return df

def fantasy_pros_ecr_draft_spread_chart(league_dict=config.sean, player_n=50, x_size=20, y_size=15):
    today = date.today()
    date_str = today.strftime('%m.%d.%Y')
    df = fantasy_pros_ecr_scrape(league_dict)
    cleaned_df = fantasy_pros_ecr_scrape_column_clean(df)
    ecr = fantasy_pros_ecr_column_reindex(cleaned_df)
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
    plt.savefig(fr'C:\Users\rmull\Documents\Rob\Python Projects\fantasy-football\figures\{date_str}_rangeofrankings.png')
    return plt.show()

def fantasy_pros_ecr_tier_add(df, player_n=50, cluster_n=8, random_st=7):
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
    df = df.copy()
    df_list = []
    pos_list = ['QB', 'RB', 'WR', 'TE']
    for pos in pos_list:
        pos_df = df.loc[df['pos']==pos]
        #pos_df.reset_index(inplace=True, drop=True)
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
    today = date.today()
    date_str = today.strftime('%m.%d.%Y')
    df = fantasy_pros_ecr_scrape(league_dict)
    cleaned_df = fantasy_pros_ecr_scrape_column_clean(df)
    ecr = fantasy_pros_ecr_column_reindex(cleaned_df)
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
    #plt.savefig(fr'C:\Users\rmull\Documents\Rob\Python Projects\fantasy-football\figures\{date_str}_rangeofrankings_tiers.png')
    return plt.show()

def fantasy_pros_ecr_draft_spread_chart_with_tiers_by_pos(league_dict=config.sean, player_n=50, x_size=20, y_size=15):
    today = date.today()
    date_str = today.strftime('%m.%d.%Y')
    pos_list = ['QB', 'RB', 'WR', 'TE']
    df = fantasy_pros_ecr_scrape(league_dict)
    cleaned_df = fantasy_pros_ecr_scrape_column_clean(df)
    ecr = fantasy_pros_ecr_column_reindex(cleaned_df)
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
        plt.xlabel('Average Expert Rank')
        plt.ylabel('Expert Consensus Rank')

        plt.gca().invert_yaxis()
        fig.set_size_inches(x_size, y_size)
        plt.savefig(fr'C:\Users\rmull\Documents\Rob\Python Projects\fantasy-football\figures\{date_str}_rangeofrankings_tiers_{pos}.png')
    return plt.show()


if __name__ == "__main__":

    DATA_DIR = r'C:\Users\rmull\Documents\Rob\Python Projects\fantasy-football\data\raw'
    league = config.sean
    pos_list = ['qb', 'wr', 'te', 'rb']
    today = date.today()
    date = today.strftime('%Y.%m.%d')
    weekly_stats = pd.read_csv(path.join(DATA_DIR, r'Game by Game Breakdown_2019_2019.csv'))
    errors_list = []
    try:
        print('Pulling in position projections...')
        df_list = []
        for pos in pos_list:
            url = f'https://www.fantasypros.com/nfl/projections/{pos}.php?week=draft&scoring=PPR&week=draft'
            scraped_df = fantasy_pros_scrape(url)
            cleaned_df = fantasy_pros_column_clean(scraped_df)
            cleaned_df['pos'] = pos.upper()
            cleaned_df = config.unique_id_create(cleaned_df, 'player_name', 'pos', 'tm')
            cleaned_df = config.char_replace(cleaned_df, 'id')
            cleaned_reindexed_df = fantasy_pros_column_reindex(cleaned_df)
            cleaned_reindexed_df['std_scoring'] = cleaned_reindexed_df['ppr_scoring'] - cleaned_reindexed_df['receiving_rec']
            cleaned_reindexed_df['half_ppr_scoring'] = cleaned_reindexed_df['ppr_scoring'] - 0.5*cleaned_reindexed_df['receiving_rec']
            cleaned_reindexed_df = config.fantasy_pros_pts(cleaned_reindexed_df, league)
            df_list.append(cleaned_reindexed_df)
        fantasy_pros_df = pd.concat(df_list)
        fantasy_pros_df.sort_values(f'{league.get("name")}_custom_pts', ascending=False, inplace=True)

    except Exception as e:
        # Store the url and the error it causes in a list
        error =[e]  
        # then append it to the list of errors
        errors_list.append(error)

    print('Pulling in ADP...')

    adp_df = ffcalculator.adp_scrape(league)
    adp_df = ffcalculator.adp_column_clean(adp_df, league)

    #combines DFs
    merged_df = fantasy_pros_df.merge(adp_df, how='left', on='id').sort_values('adp').reset_index(drop=True)
    merged_df.drop(columns=['name', 'pos_y', 'team', 'id'], inplace=True)
    merged_df.rename(columns={'pos_x' : 'pos'}, inplace=True)


    #create new id for previous season aggs
    merged_df = config.unique_id_create(merged_df, 'player_name', 'pos')
    merged_df = config.char_replace(merged_df, 'id')

    #import last season aggs
    print("Grabbing last season's aggs...")                   
    weekly_stats.columns = [col.lower() for col in weekly_stats.columns]

    #new id omits team name to prevent players with new teams from breaking the merge
    weekly_stats = config.unique_id_create(weekly_stats, 'player_name', 'pos')
    year = weekly_stats['year'].max()
    weekly_stats = config.char_replace(weekly_stats, 'id')
    weekly_stats = config.pro_football_reference_pts(weekly_stats, league)
    agg_df = weekly_stats.groupby('id').agg(
        avg_ppg =(f'{league.get("name")}_custom_pts', 'mean'),
        std_dev=(f'{league.get("name")}_custom_pts', 'std')
        )
    agg_df.rename(columns={'avg_ppg' : f'{year}_avg_ppg', 'std_dev' : f'{year}_std_dev'}, inplace=True)

    merged_df = merged_df.merge(agg_df, how='left', on='id').reset_index(drop=True)
    merged_df.drop(columns=['id'], inplace=True)


    #run the desired VBD function to calculate replacement player
    replacement_value = config.value_over_last_starter(merged_df, league, pos_list)

    #map replacement value to df and calculate value above replacement
    print('Mapping VBD...')
    merged_df[f'{league.get("name")}_custom_pts_vor'] = merged_df[f'{league.get("name")}_custom_pts'] - merged_df['pos'].map(replacement_value)
    merged_df.sort_values(f'{league.get("name")}_custom_pts_vor', inplace=True, ascending=False)
    merged_df.reset_index(drop=True)

    #export to CSVs
    merged_df[['player_name', 'tm', 'pos', 'bye', 'adp', f'{year}_avg_ppg', f'{year}_std_dev', f'{league.get("name")}_custom_pts', f'{league.get("name")}_custom_pts_vor']].to_csv(path.join(DATA_DIR, f'Fantasy_Pros_Projections_{date}_with_VOR_Condensed_{league.get("name")}.csv'), index=False)

    rows, cols = merged_df.shape
    print(f'All done! The dataframe has {rows} rows and {cols} columns.')
    error_list_len = len(errors_list)
    print(f'There were {error_list_len} errors.\n The error list is: {errors_list}.')
    print(merged_df.head())