from .base_factory import BaseFactory


class ConnectorFactory(BaseFactory):
    modules = {'requests': 'fantasyfootball.connectors.requests_connector', 'github': 'fantasyfootball.connectors.github_connector', 'selenium': 'fantasyfootball.connectors.selenium_connector', 'sql': 'fantasyfootball.connectors.sql_connector'}
