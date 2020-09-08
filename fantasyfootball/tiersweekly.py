#tiersweekly.py

from fantasyfootball import tiers
from fantasyfootball import fantasypros as fp
from fantasyfootball import config

if __name__ == "__main__":
    #run elbow chart or AIC/BIC chart to estimate optimal number of k for each pos
    #revisit week 1 to see if URL changes for each week - if so, refactor viz func and fp df func

    league = config.sean
    
    pos_tier_dict_viz = {
    'RB' : 8,
    'QB' : 6,
    'WR' : 5,
    'TE' : 5,
    'DST' : 6,
    'K' : 7
    }

    tiers.make_clustering_viz(tier_dict=pos_tier_dict_viz, league=league, pos_n=35, covariance_type='diag', draft=False, save=False)