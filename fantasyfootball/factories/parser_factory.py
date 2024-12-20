from typing import Any
import logging
from fantasyfootball.factories.base_factory import BaseFactory

logger = logging.getLogger(__name__)

class ParserFactory(BaseFactory):
    """
    Factory object used to separate connector creation from use.

    Will return any connection object that has been registered with the BaseFactory decorator when a registration key is passed.
    Requires the connectors module to be imported to trigger registration.
    """
    
    registry = {}