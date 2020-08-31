# ffcalculator.py

from bs4 import BeautifulSoup
import pandas as pd
import requests
import fantasyfootball.config as config

def adp_scrape(league):
    """Function to pull ADP table from Fantasy Football Calculator specific to customized league specs"""
    team_number = league['team_n']
    scoring = league['scoring']
    if scoring == 'standard' and team_number == 12:
        url = 'https://fantasyfootballcalculator.com/adp'
    elif scoring !='standard' and team_number == 12:
        url = f'https://fantasyfootballcalculator.com/adp/{scoring}'
    else:
        url = f'https://fantasyfootballcalculator.com/adp/{scoring}/{team_number}-team/all'
    r = requests.get(url)
    adp = BeautifulSoup(r.content, 'html.parser')
    table = adp.find_all('table')
    df = pd.read_html(str(table))[0]
    df = df.iloc[:,:-1]
    return df

def adp_column_clean(df, league):
    """Cleans ADP dataframe from Fantasy Football Calculator"""
    df = df.copy()
    df.columns = [col.lower() for col in df.columns]
    df['scoring'] = league.get('scoring')
    df['n_teams'] = league.get('team_n')
    df.rename(columns={'#':'adp', 'name': 'player_name'}, inplace=True)
    return df

def adp_process(league):
    df = adp_scrape(league)
    df = adp_column_clean(df, league)
    return df

if __name__ == "__main__":
    league = config.sean
    adp_process(league)