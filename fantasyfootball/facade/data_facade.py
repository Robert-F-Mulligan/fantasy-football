"""Configuration-driven ingestion facade with no import-time I/O."""

import argparse
import json
from pathlib import Path
from importlib.resources import files
from fantasyfootball.factories.strategy_factory import StrategyFactory


def load_config(path=None):
    resource = (
        Path(path) if path else files("fantasyfootball").joinpath("data_config.json")
    )
    return json.loads(resource.read_text(encoding="utf-8-sig"))


class DataFacade:
    def __init__(self, config, strategy_factory=None):
        self.config = config
        self.strategy_factory = strategy_factory or StrategyFactory

    def get_data(self, dataset_name, output_mode="df", **kwargs):
        if output_mode not in {"df", "csv", "db"}:
            raise ValueError("output_mode must be df, csv or db")
        try:
            dataset = self.config["datasets"][dataset_name]
            source = self.config["datasources"][dataset["datasource"]]
        except KeyError as exc:
            raise ValueError(
                f"Invalid dataset configuration for {dataset_name!r}: {exc}"
            ) from exc
        combined = {**source, **dataset, "dataset_name": dataset_name}
        strategy = self.strategy_factory.create(
            combined["strategy"], combined_config=combined, **kwargs
        )
        return strategy.run(
            output_mode=output_mode, sleep=kwargs.get("request_delay", 5)
        )

    def list_available_datasets(self):
        return sorted(self.config["datasets"])


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fetch configured fantasy football data"
    )
    parser.add_argument("--config")
    parser.add_argument("--dataset_name")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--output-mode", choices=["df", "csv", "db"], default="df")
    args = parser.parse_args(argv)
    facade = DataFacade(load_config(args.config))
    if args.list or not args.dataset_name:
        print("\n".join(facade.list_available_datasets()))
    else:
        result = facade.get_data(args.dataset_name, output_mode=args.output_mode)
        if result is not None:
            print(result.to_string(index=False))


if __name__ == "__main__":
    main()
