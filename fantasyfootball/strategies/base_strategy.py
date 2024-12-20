from abc import ABC, abstractmethod
from typing import Any
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class BaseStrategy(ABC):
    def __init__(self, config: dict[str, Any], **kwargs):
        """
        Initialize the strategy with its configuration.
        :param config: Strategy-specific configuration.
        :param kwargs: Additional parameters for the strategy.
        """
        self.config = config
        self.kwargs = kwargs

    @abstractmethod
    def run(self) -> Any:
        """Execute the strategy and return the data."""
        pass