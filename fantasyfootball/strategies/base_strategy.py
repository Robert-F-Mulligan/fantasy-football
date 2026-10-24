"""Template-method ingestion: shared lifecycle, validation and output handling."""
from abc import ABC, abstractmethod
import csv
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
import pandas as pd
from fantasyfootball.factories.connector_factory import ConnectorFactory
from fantasyfootball.factories.datasource_factory import DatasourceFactory
from fantasyfootball.factories.parser_factory import ParserFactory
from fantasyfootball.factories.transformer_factory import TransformerFactory


class BaseStrategy(ABC):
    def __init__(self, combined_config, **kwargs):
        self.combined_config = {**combined_config, **kwargs}
        self.time_now = datetime.now()
        self.all_data = []
        self.sql_connector = None
        self._load_config()
        self.output_modes = {'csv': self.save_to_csv, 'db': self.publish_to_database, 'df': self.append_to_df}

    def _load_config(self):
        cfg = self.combined_config
        for key, value in cfg.items():
            if key not in {'connector', 'parser', 'datasource', 'transformer'}:
                if key.startswith('_') or hasattr(type(self), key):
                    raise ValueError(f'Reserved configuration key: {key}')
                setattr(self, key, value)
        self.connector = ConnectorFactory.create(cfg['connector'], base_url=cfg.get('base_url')) if cfg.get('connector') else None
        self.parser = ParserFactory.create(cfg['parser']) if cfg.get('parser') else None
        self.datasource = DatasourceFactory.create(cfg['datasource']) if cfg.get('datasource') else None
        self.transformer = TransformerFactory.create(cfg['transformer']) if cfg.get('transformer') else None

    @abstractmethod
    def iter_frames(self, connector, sleep=0):
        """Yield processed frames. Errors propagate; partial results are never success."""
        raise NotImplementedError

    def run(self, output_mode='df', sleep=0):
        if output_mode not in self.output_modes:
            raise ValueError(f'Unknown output mode: {output_mode}')
        if sleep < 0:
            raise ValueError('sleep must be nonnegative')
        self.all_data = []
        context = self.connector if hasattr(self.connector, '__enter__') else nullcontext(self.connector)
        written = False
        try:
            with context as connector:
                for frame in self.iter_frames(connector, sleep=sleep):
                    if not isinstance(frame, pd.DataFrame):
                        raise TypeError('Strategies must yield pandas DataFrames')
                    if frame.empty:
                        continue
                    self.output_modes[output_mode](frame, append=written)
                    written = True
        finally:
            if self.sql_connector is not None:
                self.sql_connector.__exit__(None, None, None)
                self.sql_connector = None
        if output_mode == 'df':
            return pd.concat(self.all_data, ignore_index=True) if self.all_data else pd.DataFrame()
        return None

    def years(self):
        low, high = self.combined_config.get('min_year'), self.combined_config.get('max_year')
        if not isinstance(low, int) or not isinstance(high, int) or low > high:
            raise ValueError('min_year and max_year must be ordered integers')
        return range(low, high + 1)

    def publish_to_database(self, data, append=False, **kwargs):
        if self.sql_connector is None:
            self.sql_connector = ConnectorFactory.create('sql')
        self.sql_connector.publish(data.assign(created_at=self.time_now),
                                   table_name=self.dataset_name,
                                   if_exists='append' if append else self.combined_config.get('if_exists', 'append'),
                                   schema=self.combined_config.get('schema', 'source'),
                                   chunksize=self.combined_config.get('chunksize'))

    def save_to_csv(self, data, append=False, **kwargs):
        filename = self.combined_config.get('output_path', f'{self.get_filename()}_{self.time_now:%Y-%m-%d}.csv')
        path = Path(filename)
        # CSV headers are strings. Validate before opening the file for writing,
        # including collisions caused by stringifying non-string column labels.
        columns = data.columns.map(str)
        if columns.has_duplicates:
            raise ValueError('CSV frames must have unique column names')
        frame = data.set_axis(columns, axis=1)
        if append:
            with path.open(encoding='utf-8', newline='') as stream:
                header = next(csv.reader(stream), [])
            if len(header) != len(set(header)) or set(columns) != set(header):
                raise ValueError('CSV columns do not match the existing header')
            frame = frame.loc[:, header]
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, mode='a' if append else 'w', header=not append, index=False)


    def append_to_df(self, data, append=False, **kwargs):
        if not append:
            self.all_data = []
        self.all_data.append(data.copy())

    def get_filename(self, *args):
        return '_'.join([f'{self.dataset_name}_strategy', *map(str, args)])
