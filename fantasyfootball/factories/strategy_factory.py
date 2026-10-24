from .base_factory import BaseFactory


class StrategyFactory(BaseFactory):
    modules = {'fantasypros': 'fantasyfootball.strategies.fantasypros_strategy', 'nflfastr': 'fantasyfootball.strategies.nflfastr_strategy', 'year_by_year': 'fantasyfootball.strategies.pfr_yby_strategy', 'game_by_game': 'fantasyfootball.strategies.pfr_gbg_strategy'}
