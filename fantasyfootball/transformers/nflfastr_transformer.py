import pandas as pd
import logging
from fantasyfootball.transformers.base_transformer import BaseTransformer
from fantasyfootball.factories.transformer_factory import TransformerFactory

logger = logging.getLogger(__name__)

@TransformerFactory.register('nflfastr')
class NflfastrTransfomer(BaseTransformer):
    """Encapsulates transformation logic for ranking data."""

    def __init__(self, dataframe: pd.DataFrame = None):
        """
        Initializes the transformer with optional DataFrame.
        :param dataframe: The DataFrame to transform (optional).
        """
        super().__init__(dataframe)

    def transform(self, dataframe: pd.DataFrame = None) -> pd.DataFrame:
        """Performs the entire transformation process."""
        if dataframe is not None:
            self.dataframe = dataframe

        if self.dataframe is None:
            raise ValueError("No DataFrame set for transformation.")

        logger.info("Starting Nflfastr transformation process.")
        return (
            self._convert_ids()
                .dataframe
        )

    def _convert_ids(self):
        logger.debug("Converting player IDs to objects.")
        for column in self.dataframe.columns:
            if column.endswith('_id'):
                self.dataframe[column] = self.dataframe[column].astype('object')
        return self