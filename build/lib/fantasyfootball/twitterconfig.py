#twitterconfig.py

from dotenv import load_dotenv
import os
import requests

env_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))),'.env') 

load_dotenv(env_path)

class TwitterConfig:
    SEARCH_BASE_URL = "https://api.twitter.com/1.1/search/tweets.json"

    TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
    TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
    TWITTER_CONSUMER_KEY = os.getenv('TWITTER_CONSUMER_KEY')
    TWITTER_CONSUMER_KEY_SECRET = os.getenv('TWITTER_CONSUMER_KEY_SECRET')

    ANALYSTS = {
        'Matthew Berry': 'MatthewBerryTMR', #ESPN
        'Field Yates': 'FieldYates', #ESPN
        'NFL Fantasy Football': 'NFLFantasy',
        'PFF Fantasy Football': 'PFF_Fantasy',
        'FantasyPros': 'FantasyPros',
        'Sean Koerner': 'The_Oddsmaker', #FantasyLabs
        'Chris Raybon': 'ChrisRaybon', #ESPN+
        'Ian Hartitz': 'IHartitz', #FantasyLabs
        'FantasyLabs NFL': 'FantasyLabsNFL', #FantasyLabs
        'Adam Levitan': 'AdamLevitan', #DraftKings
        'Peter Jennings': 'CSURAM88', #FantasyLabs
        'Jonathan Bales': 'BalesFootball', #FantasyLabs
        'Rich Hribar': 'LordReebs', #Rotoworld
        'Graham Barfield': 'GrahamBarfield', #Fantasy Guru
        'Matt Harmon': 'MattHarmon_BYB', #Yahoo
        'Cynthia Frelund': 'CFrelund', #NFL Network
        'Evan Silva': 'evansilva', #Esatablish The Run
        'Adan Schefter': 'AdamSchefter', #ESPN
        'Warren Sharp': 'SharpFootball'
    }

if __name__ == "__main__":
    print(env_path)