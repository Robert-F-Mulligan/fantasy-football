#pfradv.py

import pandas as pd
import requests
from bs4 import BeautifulSoup
from os import path
import fantasyfootball.pfr as pfr

def advanced_player_soup_grab(last_name_letter, player_id, year):
    """Returns a soup object for Advanced stats for each player in a given year"""
    advanced_season_url = f'https://www.pro-football-reference.com/players/{last_name_letter}/{player_id}/gamelog/{year}/advanced/'
    r_player = requests.get(advanced_season_url)
    soup = BeautifulSoup(r_player.content, 'html.parser')
    return soup

def advanced_date_extract(soup):
    """Extracts the dates for the advanced stats data"""
    date_table = soup.find_all('table')
    date_df = pd.read_html(str(date_table))[0]
    date_df.columns = date_df.columns.droplevel(level=0)
    date_df.columns = [col.lower() for col in date_df.columns]
    date_df = date_df['date']
    return date_df

def advanced_stats_table(soup):
    """Parses a soup object for advanced_passing and advanced_rushing_and_receiving tables"""
    passing_table = soup.find('table', id='advanced_passing')
    rush_rec_table = soup.find('table', id='advanced_rushing_and_receiving')
    return passing_table, rush_rec_table

def advanced_stats_transformation(passing_table, rush_rec_table):
    """Converts and combines the passing table and rush_rec table into one big dataframe"""
    advanced_rushing_rec_col = ['rushing_1d', 'rushing_ybc', 'rushing_yac', 'rushing_brktkl', 'receiving_1d', 'receiving_ybc', 'receiving_yac', 'receiving_brktkl', 'receiving_drop']
    advanced_passing = ['passing_1d', 'passing_iay', 'passing_cay', 'passing_yac', 'passing_drops', 'passing_badth', 'passing_bltz', 'passing_hrry', 'passing_hits', 'passing_scrm']
    if passing_table is None:
        advanced_passing_df = pd.DataFrame(columns=advanced_passing)
    else:
        advanced_passing_df = pd.read_html(str(passing_table))[0]
        advanced_passing_df.columns = ['_'.join(col) for col in advanced_passing_df.columns]
        advanced_passing_df.columns = [col.lower() for col in advanced_passing_df.columns]
        advanced_passing_df = advanced_passing_df.reindex(columns=advanced_passing, fill_value=0)

    if rush_rec_table is None:
        advanced_rush_rec_df = pd.DataFrame(columns=advanced_rushing_rec_col)
    else:
        advanced_rush_rec_df = pd.read_html(str(rush_rec_table))[0]
        advanced_rush_rec_df.columns = ['_'.join(col) for col in advanced_rush_rec_df.columns]
        advanced_rush_rec_df.columns = [col.lower() for col in advanced_rush_rec_df.columns]
        advanced_rush_rec_df = advanced_rush_rec_df.reindex(columns=advanced_rushing_rec_col, fill_value=0)
    joined_df = advanced_rush_rec_df.join(advanced_passing_df)
    return joined_df

def advanced_stats_reindex(df):
    """Reorders the columns and replaces nans with 0's"""
    df = df.copy()
    user_added = ['player_id', 'player_name', 'pos', 'date', 'year']
    advanced_rushing_rec_col = ['rushing_1d', 'rushing_ybc', 'rushing_yac', 'rushing_brktkl', 'receiving_1d', 'receiving_ybc', 'receiving_yac', 'receiving_brktkl', 'receiving_drop']
    advanced_passing = ['passing_1d', 'passing_iay', 'passing_cay', 'passing_yac', 'passing_drops', 'passing_badth', 'passing_bltz', 'passing_hrry', 'passing_hits', 'passing_scrm']
    full_column_List = user_added + advanced_rushing_rec_col + advanced_passing
    reindexed_df = df.reindex(columns = full_column_List, fill_value = 0)
    reindexed_df.fillna(0, inplace=True)
    return reindexed_df

if __name__ == "__main__":
    min = 2019
    max = 2019
    row_n = 300

    DATA_DIR = r'C:\Users\rmull\Documents\Rob\Python Projects\Fantasy Football\data\raw'

    df_list = []

    errors_list = []

    for year in range(min, max+1):

        href_list = pfr.player_href_list_grab(year)

        for href in href_list[:row_n]:

            last_name_letter, player_id = pfr.player_id_transform(href)
            
            try:
                soup = advanced_player_soup_grab(last_name_letter, player_id, year)
                player_name, pos = pfr.player_name_and_pos_grab(soup)
                passing_table, rush_rec_table = advanced_stats_table(soup)
                date_df = advanced_date_extract(soup)
                transformed_df = advanced_stats_transformation(passing_table, rush_rec_table)                      
                transformed_df = transformed_df.join(date_df)
                transformed_df = transformed_df[:-1]
                transformed_df = pfr.player_table_variable_add(transformed_df, player_id, pos, year, player_name)
                transformed_df = advanced_stats_reindex(transformed_df)
                df_list.append(transformed_df)
            
            except Exception as e:
                # Store the url and the error it causes in a list
                error =[year, href, pos, player_name, e] 
                errors_list.append(error)

    df = pd.concat(df_list)

    rows, cols = df.shape

    df.head()

    df.to_csv(path.join(DATA_DIR, f'Advanced Stats Game by Game Breakdown_{min}_{max}.csv'), index=False)

    print(f'All done! The dataframe has {rows} rows and {cols} columns.')

    error_list_len = len(errors_list)

    print(f'There were {error_list_len} errors.\n The error list is: {errors_list}.')
