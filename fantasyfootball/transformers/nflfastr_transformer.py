import pandas as pd
import logging
from fantasyfootball.transformers.base_transformer import BaseTransformer
from fantasyfootball.factories.transformer_factory import TransformerFactory

logger = logging.getLogger(__name__)

@TransformerFactory.register('nflfastr')
class NflfastrTransfomer(BaseTransformer):
    """Encapsulates transformation logic for ranking data."""
    COLUMN_DTYPES = {
        'desc': str,
        'yrdln': str,
        'time': str,
        'time_of_day': str,
        'end_clock_time': lambda x: pd.to_datetime(x, errors='coerce'),
        'drive_real_start_time': lambda x: pd.to_datetime(x, errors='coerce'),
        'drive_time_of_possession': str,
        'drive_game_clock_start': str,
        'drive_game_clock_end': str,
        'drive_start_yard_line': str,
        'drive_end_yard_line': str,
        'side_of_field': str,
        'yrdln': str,
        'pass_length': str,
        'run_gap': str,
        'weather': str,
        'surface': str,
        'passer': str,
        'rusher': str,
        'receiver': str,
        'fantasy': str

    }

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
            self._convert_dtypes()
                .dataframe
        )

    def _convert_dtypes(self):
        logger.debug("Converting player IDs to objects.")
        target_suffixes = ('id', 'name', 'team', 'type', 'location', 'result', 'transition')

        for column, dtype in self.COLUMN_DTYPES.items():
            if column in self.dataframe.columns:
                if callable(dtype):  # If dtype is a function (e.g., lambda)
                    self.dataframe[column] = self.dataframe[column].apply(dtype)
                else:  # For standard dtypes like str, int, float, etc.
                    self.dataframe[column] = self.dataframe[column].astype(dtype)

        # Convert other columns ending with specific suffixes
        for column in self.dataframe.columns:
            if column.endswith(target_suffixes):
                self.dataframe[column] = self.dataframe[column].astype(str)

        return self