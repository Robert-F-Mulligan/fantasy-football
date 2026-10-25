from .base_factory import BaseFactory


class TransformerFactory(BaseFactory):
    modules = {'nflfastr': 'fantasyfootball.transformers.nflfastr_transformer', 'fantasy_pros_rankings': 'fantasyfootball.transformers.fantasypros_transformer', 'fantasy_pros_projections': 'fantasyfootball.transformers.fantasypros_transformer', 'fantasy_pros_draft': 'fantasyfootball.transformers.fantasypros_transformer', 'prf_year_by_year': 'fantasyfootball.transformers.profootballreference_transformer', 'prf_game_by_game': 'fantasyfootball.transformers.profootballreference_transformer'}
