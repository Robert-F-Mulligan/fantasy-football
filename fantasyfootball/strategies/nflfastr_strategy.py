from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.factories.strategy_factory import StrategyFactory
import pandas as pd


@StrategyFactory.register('nflfastr')
class NflfastrStrategy(BaseStrategy):
    def iter_frames(self, connector, sleep=0):
        for year in self.years():
            endpoint = self.endpoint_template.format(year=year)
            raw = self.datasource.get_data(connector=connector, endpoint=endpoint,
                                           chunksize=self.combined_config.get('chunksize'))
            try:
                chunks = [raw] if isinstance(raw, pd.DataFrame) else raw
                for chunk in chunks:
                    yield self.transformer.transform(chunk.copy())
            finally:
                if not isinstance(raw, pd.DataFrame) and hasattr(raw, 'close'):
                    raw.close()
