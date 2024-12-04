import logging
from abc import ABC, abstractmethod
import pandas as pd

logger = logging.getLogger(__name__)

class BaseTransformer(ABC):
    """
    Abstract base class for data cleaning and preparation.
    """

    def __init__(self, dataframe: pd.DataFrame):
        """
        Initialize the transformer with a DataFrame.
        :param dataframe: The DataFrame to be transformed.
        """
        self.dataframe = dataframe

    @abstractmethod
    def transform(self) -> pd.DataFrame:
        """
        Transform the DataFrame. This method must be implemented in subclasses.
        :return: Transformed DataFrame.
        """
        pass