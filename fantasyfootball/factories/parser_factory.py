from .base_factory import BaseFactory


class ParserFactory(BaseFactory):
    modules = {'html': 'fantasyfootball.parsers.html_parser'}
