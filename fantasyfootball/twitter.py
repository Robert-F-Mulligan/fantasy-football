# twitter.py

from fantasyfootball.twitterconfig import TwitterConfig
from requests_oauthlib import OAuth1
from urllib import parse
import requests
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import pandas as pd
from datetime import date
from os import path
import sys
from ffcalculator import adp_scrape
import config as ffconfig

config = TwitterConfig()

def generate_oauth1():
    """Generates a token for Twitter API """
    token = OAuth1(
        config.TWITTER_CONSUMER_KEY,
        config.TWITTER_CONSUMER_KEY_SECRET,
        config.TWITTER_ACCESS_TOKEN,
        config.TWITTER_ACCESS_TOKEN_SECRET
    )
    return token

def twitter_search_url_constructor(search, base_url=config.SEARCH_BASE_URL, account_dict=config.ANALYSTS):
    """Constructs a search URL for Twitter API using a search criteria and an account dict """
    url = base_url + '?q='
    from_accounts = 'from:'
    for i, account in enumerate(account_dict.values()):
        if i == 0:
            from_accounts = from_accounts + account
        else:
            from_accounts = from_accounts + ' OR ' + account
    search_values = ''
    for i, val in enumerate(search):
        if i == 0:
            search_values = search_values + val
        else:
            search_values = search_values + ' OR ' + val
    first_query = parse.quote(from_accounts + search_values)
    url = url + first_query
    return url

def search_parameter_generator(count=100, language='en', entity_bool=False):
    """Genrates search parameters for Twitter API search """
    SEARCH_PARAMS = {
        'count': count, 
        'lang': language,
        'include_entities': entity_bool
    }
    return SEARCH_PARAMS

def twitter_api_request(url, parameters, token):
    """Returns a list of tweets"""
    res = requests.get(
        url,
        params=parameters,
        auth=token
    )
    tweets = res.json().get('statuses')
    return tweets

def parse_tweets(tweets):
    """Cleans up tweet list"""
    parsed_tweets = []
    for tweet in tweets:
        if tweet is None:
            continue
        else:
            truncated = tweet.get('truncated')
            text = tweet.get('text')
            reply = tweet.get('in_reply_to_status_id')
            if not truncated and 'RT' not in text and reply is None:
                parsed_tweets.append(text)
    return parsed_tweets

def generate_player_list(df):
    """Generates player and pos list given a DF"""
    df = df.copy()
    player_list = df['Name'].to_list()
    pos_list = df['Pos'].to_list()
    return player_list, pos_list

def format_player_list(player_list):
    """Takes a list of players and returns a more robust search list"""
    formatted_names = []
    for player in player_list:
        split_name = player.split(' ')
        name_one = player
        name_two = '.'.join([split_name[0][0], ' '+split_name[-1]]) # player's first initial, last name
        formatted_names.append([name_one, name_two])
    return formatted_names

def generate_sentiment_dict(formatted_names):
    """Generates sentiement dict""" 
    sentiment_dict = {}
    for player in formatted_names:
        url = twitter_search_url_constructor(player)
        tweets = twitter_api_request(url, params, token)
        parsed_tweets = parse_tweets(tweets)

        sentiment_dict[player[0]] = {
            'positive': 0,
            'negative': 0,
            'neutral': 0,
            'compound': 0,
            'num_tweets' : 0
        }
        sid = SentimentIntensityAnalyzer()
        for tweet in parsed_tweets:
            polarity_score = sid.polarity_scores(tweet)
            sentiment_dict[player[0]]['positive'] += polarity_score.get('pos')
            sentiment_dict[player[0]]['negative'] += polarity_score.get('neg')
            sentiment_dict[player[0]]['neutral'] += polarity_score.get('neu')
            sentiment_dict[player[0]]['compound'] += polarity_score.get('compound')
            sentiment_dict[player[0]]['num_tweets'] += 1
    return sentiment_dict


if __name__ == '__main__':
    today = date.today()
    date = today.strftime('%Y.%m.%d')
    DATA_DIR = r'C:\Users\rmull\Documents\Rob\Python Projects\fantasy-football\data\raw'

    row_n = 170
    league = ffconfig.sean
    params = search_parameter_generator()
    token = generate_oauth1()
    adp_df = adp_scrape(league)
    adp_df = adp_df.loc[adp_df['Pos'].isin(['QB', 'RB', 'WR', 'TE'])]
    player_list, pos_list = generate_player_list(adp_df)
    formatted_names = format_player_list(player_list)
    sentiment_dict = generate_sentiment_dict(formatted_names[:row_n])
    
    df = pd.DataFrame(sentiment_dict)
    df = df.transpose()
    df.reset_index(inplace=True)
    df.rename(columns={'index' : 'player_name'}, inplace=True)
    pos_df = pd.DataFrame({'pos': pos_list[:row_n]})
    df = df.join(pos_df, how="left")
    df = ffconfig.unique_id_create(df, 'player_name', 'pos')
    df = ffconfig.char_replace(df, 'id')
    df['avg_sentiment'] = df['compound'] / df['num_tweets']
    df.to_csv(path.join(DATA_DIR, f'Twitter_Sentiment_Analysis_{date}.csv'), index=False)
    
    print('All finished!')
