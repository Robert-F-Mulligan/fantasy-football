import json
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Loads configuration from a JSON file.

    Args:
        config_path (str): Path to the configuration JSON file.

    Returns:
        Dict[str, Any]: Parsed configuration as a dictionary.
    """
    with Path(config_path).open() as f:
        return json.load(f)
