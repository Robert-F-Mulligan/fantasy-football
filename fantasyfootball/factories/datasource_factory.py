from .base_factory import BaseFactory


class DatasourceFactory(BaseFactory):
    modules = {'fantasypros': 'fantasyfootball.datasources.fantasypros', 'nflfastr': 'fantasyfootball.datasources.nflfastr', 'profootballreference': 'fantasyfootball.datasources.profootballreference'}
