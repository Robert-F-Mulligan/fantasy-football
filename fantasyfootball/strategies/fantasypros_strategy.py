from itertools import product
from fantasyfootball.strategies.base_strategy import BaseStrategy
from fantasyfootball.factories.strategy_factory import StrategyFactory


@StrategyFactory.register('fantasypros')
class FantasyProsStrategy(BaseStrategy):
    def iter_frames(self, connector, sleep=0):
        positions = self.combined_config.get('positions') or [None]
        weeks = self.combined_config.get('week')
        weeks = weeks if isinstance(weeks, (list, tuple)) else [weeks]
        for pos, week in product(positions, weeks):
            endpoint = self.endpoint_template.format(position=pos or '', week='draft' if week is None else week)
            metadata = {key: value for key, value in {'pos': pos.upper() if pos else None, 'week': week}.items() if value is not None}
            yield self.get_data(connector, endpoint, self.table_id, **metadata)

    def get_data(self, connector, endpoint, table_id, **cols):
        raw = self.datasource.get_data(connector=connector, endpoint=endpoint, table_id=table_id, parser=self.parser)
        return self.transformer.transform(raw.assign(**cols))
