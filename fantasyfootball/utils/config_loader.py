import json
import os
from pathlib import Path
from typing import Any


def load_config(config_path: str) -> dict[str, Any]:
    """
    Loads configuration from a JSON file.

    Args:
        config_path (str): Path to the configuration JSON file.

    Returns:
        Dict[str, Any]: Parsed configuration as a dictionary.
    """
    with Path(config_path).open() as f:
        return json.load(f)
    
def get_team_file_paths_by_key(config: dict[str, Any], key: str) -> dict[str, str]:
    """
    Generates a dictionary mapping each team to its fully formed file path based on the specified key.

    Args:
        config (Dict[str, Any]): Loaded configuration containing directory paths and team mappings.
        key (str): The key representing the directory (e.g., "wiki", "espn", "wordmark").

    Returns:
        Dict[str, str]: Dictionary where each team abbreviation corresponds to the relative file location.
    """
    directories = config.get("directories", {})
    teams = config.get("teams", {})

    if key not in directories:
        raise ValueError(f"Key '{key}' not found in the directories section of the configuration.")

    base_dir = directories[key]

    return {
        team : os.path.join(base_dir, team_data.get(key, ""))
        for team, team_data in teams.items()
    }

if __name__ == "__main__":
    path=r'config\team_config.json'
    config = load_config(path)
    print(config)
    team_list = get_team_file_paths_by_key(config=config, key='primary_color')
    #print(team_list)
    print(team_list['NYJ'])
