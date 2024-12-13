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

    def _rename_columns(self, rename_map: dict):
        """Renames columns based on a provided mapping."""
        logger.debug("Renaming columns using provided map.")
        self.dataframe = self.dataframe.rename(columns=rename_map)
        return self

    def _drop_columns(self, columns: list = None):
        """Drops columns"""
        logger.debug("Cleaning columns: dropping unwanted columns.")
        if columns:
            self.dataframe = self.dataframe.drop(columns=columns)
        return self

    def _reindex_and_fill(self, column_order: list, fill_value=0, dtype_map: dict = None):
        """Reorders columns, fills missing values, and casts data types."""
        logger.debug("Reindexing columns and filling missing values.")
        self.dataframe = self.dataframe.reindex(columns=column_order, fill_value=fill_value).fillna(fill_value)
        if dtype_map:
            self.dataframe = self.dataframe.astype(dtype_map)
        return self
    