from abc import ABC, abstractmethod
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class BaseController:
    def __init__(self):
        """
        Base controller to orchestrate fetching, parsing, transforming, and saving data.
        """
        pass

    @abstractmethod
    def run(self) -> pd.DataFrame:
        """Orchestrates the data fetching, parsing, transforming, and saving process."""
        pass