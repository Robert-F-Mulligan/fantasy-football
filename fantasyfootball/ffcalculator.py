# ffcalculator.py

from bs4 import BeautifulSoup
import pandas as pd
import requests
import fantasyfootball.config as config

def adp_scrape(league_dict):
    """Function to pull ADP table from Fantasy Football Calculator specific to customized league specs"""
    team_number = league_dict.get('team_n')
    scoring = league_dict.get('scoring')
    if (scoring == 'standard') and (team_number == 12):
        url = 'https://fantasyfootballcalculator.com/adp'
    elif (scoring == 'ppr' or scoring == 'half-ppr')  & (team_number == 12):
        url = f'https://fantasyfootballcalculator.com/adp/{scoring}'
    elif team_number == 14:
        url = f'https://fantasyfootballcalculator.com/adp/{scoring}/{team_number}-team/all'
    r = requests.get(url)
    adp = BeautifulSoup(r.content, 'html.parser')
    table = adp.find_all('table')
    df = pd.read_html(str(table))[0]
    df = df.iloc[:,:-1]
    return df

def adp_column_clean(df, league_dict):
    """Cleans ADP dataframe from Fantasy Football Calculator"""
    df = df.copy()
    df.columns = [col.lower() for col in df.columns]
    df = config.unique_id_create(df, 'name', 'pos', 'team')
    df['scoring'] = league_dict.get('scoring')
    df['n_teams'] = league_dict.get('team_n')
    df = config.char_replace(df, 'id')
    df.rename(columns={'#':'adp'}, inplace=True)
    return df

if __name__ == "__main__":
    league = config.sean
    adp = adp_scrape(league)
    adp_clean = adp_column_clean(adp, league)