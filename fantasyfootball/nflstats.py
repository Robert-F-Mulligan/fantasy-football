import pandas as pd
from datetime import datetime
from nflfastr import get_nfl_fast_r_data, get_nfl_fast_r_roster, get_nfl_schedule_data, get_current_season_year

def filter_passing_plays(df, offense=True):
    """
    Filters out plays that do not count towards passing stats
    Includes: completed passes, incomplete passes, interceptions, downs 1-4
    :df: pass a dataframe with play-by-play data from nflfastr
    """
    comp_pass = df['complete_pass'] == 1
    inc_pass = df['incomplete_pass'] == 1
    int_pass = df['interception'] == 1
    sack = df['sack'] == 1 # to count defensive passing yards
    na_down = ~df['down'].isna()

    if offense:
        df = df.loc[(comp_pass | inc_pass | int_pass) & na_down]
    else:
        df = df.loc[(comp_pass | inc_pass | int_pass | sack) & na_down]
    return df
    
def get_passing_stats(df=None, year=None, offense=True, weekly=False):
    """
    Returns aggregate passing stats for a given NFL season
    :df: pass in a dataframe; if left blank, a new play-by-play dataframe will be generated based on the year parameter
    :year: pass in a season in order to generate the main dataframe
    :weekly: default is set to False, which is season-long aggregation; set this to True if you want to get game-by-game stats
    """
    if df is None:
        df = get_nfl_fast_r_data(year)
    
    group = ['passer_player_id']
    if not offense:
        group = ['defteam']

    if weekly:
        group.append('game_id')

    # fumbles by QB when considered a passer
    fumbles= (df.loc[df['play_type'] == 'pass']
                .assign(pass_fumbles= df.apply(lambda x: 1 if x['passer_player_id']==x['fumbled_1_player_id'] else 0,  axis='columns'))
                .groupby(group).agg(pass_fumbles=('pass_fumbles', 'sum'))
                )
    
    # filter plays that count for passing stats
    df = filter_passing_plays(df, offense=offense)

    if not offense:
        # sack yards are counted for defensive total passing yards
        pass_yards = df.groupby(group).agg(passing_yds=('yards_gained', 'sum'))
        # all other stats should mirror the opposing passer stats
        df = df.loc[df['sack'] == 0]

    
    qb = (df.assign(pass_tds= df.apply(lambda x: 1 if (x['touchdown'] ==1) & (x['td_team'] == x['posteam']) else 0, axis='columns')) # filter pick 6 and fumble return
            .groupby(group)
            .agg(passing_games=('game_id', 'nunique'),
                 passing_yds=('passing_yards', 'sum'),
                 pass_tds=('pass_tds', 'sum'),
                 interceptions=('interception', 'sum'),
                 completions=('complete_pass', 'sum'),
                 atts=('play_id', 'count'),
                 intended_pass_ay=('air_yards', 'mean')
              )
            .sort_values('passing_yds', ascending=False)
        )
    qb = pd.concat([qb, fumbles], axis='columns')
    if not offense:
        qb = qb.assign(passing_yds=pass_yards)
    return qb

def get_receiving_stats(df=None, year=None, offense=True, weekly=False):
    """
    Returns aggregate receiving stats for a given NFL season
    :df: pass in a dataframe; if left blank, a new play-by-play dataframe will be generated based on the year parameter
    :year: pass in a season in order to generate the main dataframe
    :weekly: default is set to False, which is season-long aggregation; set this to True if you want to get game-by-game stats
    """
    if df is None:
        df = get_nfl_fast_r_data(year)
    
    df = filter_passing_plays(df, offense=offense)
    
    group = ['receiver_player_id']

    if not offense:
        group = ['defteam']
        
    if weekly:
        group.append('game_id')
        
    wr = (df.assign(ez_tgts= lambda x: (x['air_yards']==x['yardline_100']))
            .groupby(group)
            .agg(rec_games=('game_id', 'nunique'),
                 rec_team=('posteam', 'last'),
                 receiving_yards=('receiving_yards', 'sum'),
                 receiving_tds=('pass_touchdown', 'sum'),
                 rec_ay=('air_yards', 'sum'),
                 adot=('air_yards', 'mean'),
                 targets=('play_id', 'count'),
                 rec=('complete_pass', 'sum'),
                 rec_fumbles=('fumble', 'sum'),
                 rz_tgts=('yardline_100', lambda x: (x <= 20).sum()),
                 ez_tgts=('ez_tgts', 'sum')
              )
             .assign(target_share= lambda x: x['targets'] / x.groupby('rec_team')['targets'].transform('sum') * 100,
                    yards_per_rec= lambda x: x['receiving_yards'] / x['rec'],
                    ay_share= lambda x: x['rec_ay'] / x.groupby('rec_team')['rec_ay'].transform('sum') * 100,
                    ay_pg= lambda x: x['rec_ay'] / x['rec_games'],
                    catch_rate= lambda x: x['rec']/x['targets'] * 100,
                    #rz_tgt_pg= lambda x: x['rz_tgts'] / x['rec_games'],
                    #ez_tgt_pg= lambda x: x['ez_tgts'] / x['rec_games'],
                    #rec_tds_pg= lambda x: x['receiving_tds'] / x['rec_games']
                    )
             .sort_values('receiving_yards', ascending=False)
        )
    return wr

def get_rushing_stats(df=None, year=None, offense=True, weekly=False):
    """
    Returns aggregate rushing stats for a given NFL season
    :df: pass in a dataframe; if left blank, a new play-by-play dataframe will be generated based on the year parameter
    :year: pass in a season in order to generate the main dataframe
    :weekly: default is set to False, which is season-long aggregation; set this to True if you want to get game-by-game stats
    """
    if df is None:
        df = get_nfl_fast_r_data(year)
    
    group = ['rusher_player_id']

    if not offense:
        group = ['defteam']
        
    if weekly:
        group.append('game_id')
        
    rb = (df.assign(rush_fumbles= df.apply(lambda x: 1 if x['fumbled_1_player_id'] == x['rusher_player_id'] else 0, axis='columns'))
            .groupby(group)
            .agg(rush_games=('game_id', 'nunique'),
                 rush_team=('posteam', 'last'),
                 rushing_yards=('rushing_yards', 'sum'),
                 rushing_tds=('rush_touchdown', 'sum'),
                 att=('play_id', 'count'),
                 rush_fumbles=('rush_fumbles', 'sum'),
                 pos_run_rate=('yards_gained', lambda x: (x > 0).mean() * 100),
                att_5_yd_rate=('yardline_100', lambda x: (x <= 5).mean() * 100),
                #att_5_yd=('yardline_100', lambda x: (x <= 5).sum()),
                att_2_yd_rate=('yardline_100', lambda x: (x <= 2).mean() * 100) 
              )
             .assign(carry_share= lambda x: x['att'] / x.groupby('rush_team')['att'].transform('sum') * 100,
                    yards_share= lambda x: x['rushing_yards'] / x.groupby('rush_team')['rushing_yards'].transform('sum') * 100,
                    ypc= lambda x: x['rushing_yards'] / x['att'],
                    td_rate= lambda x: x['rushing_tds'] / x['att'] * 100)
             .sort_values('rushing_yards', ascending=False)
        )
    return rb

def get_player_name_and_pos(year=None):
    if year is None:
        year = get_current_season_year()
    return (get_nfl_fast_r_roster(year).groupby(['gsis_id'])
                                       .agg(name=('full_name', 'last'),
                                            team=('team', 'last'),
                                            pos=('position', 'last'))
                                        .dropna()
            )

def combine_pass_rec_rush_stats(df=None, year=None, offense=True, weekly=False, pos=None):
    if year is None:
        year = get_current_season_year()
    df_dict = {}
    if offense:
        df_dict['roster'] = get_player_name_and_pos(year=year)
        cols = ['name', 'team', 'pos', 'games']
    else:
        df_dict['roster'] = pd.DataFrame(df['defteam'].unique(), columns=['team'])
        cols = ['games']
    df_dict['qb'] = get_passing_stats(df=df, year=year, offense=offense, weekly=weekly)
    df_dict['wr'] = get_receiving_stats(df=df, year=year, offense=offense, weekly=weekly)
    df_dict['rb'] = get_rushing_stats(df=df, year=year, offense=offense, weekly=weekly)

    df =  pd.concat([df for k, df in df_dict.items()], axis='columns')

    # fumbles
    fumbles = pd.DataFrame(df.filter(regex='fumble').sum(axis='columns'), columns=['fumbles'])
    # games played
    games = pd.DataFrame(df.filter(regex='games').max(axis='columns'), columns=['games'])
    # touchdowns

    df = pd.concat([df, fumbles, games], axis='columns')

    if pos.lower() == 'qb':
        qb_cols = ['passing_yds', 'pass_tds', 'rushing_tds', 'rushing_yards', 'interceptions','completions', 'atts', 'intended_pass_ay', 'fumbles']
        df = df.loc[:, cols + qb_cols].sort_values('passing_yds', ascending=False)
    elif pos.lower() == 'rb':
        rb_cols = ['rushing_yards', 'rushing_tds', 'receiving_yards', 'receiving_tds', 'att', 'pos_run_rate', 'att_5_yd_rate', 'att_2_yd_rate', 'carry_share', 'yards_share', 'ypc', 'td_rate', 'fumbles']
        df = df.loc[:, cols + rb_cols].sort_values('rushing_yards', ascending=False)
    elif pos.lower() == 'wr':
        wr_cols = ['receiving_yards', 'receiving_tds', 'rushing_yards', 'rushing_tds', 'rec_ay', 'adot', 'targets', 'rec',
                   'rz_tgts', 'ez_tgts', 'target_share', 'yards_per_rec', 'ay_share',
                   'catch_rate', 'fumbles']
        df = df.loc[:, cols + wr_cols].sort_values('receiving_yards', ascending=False)
    return df
