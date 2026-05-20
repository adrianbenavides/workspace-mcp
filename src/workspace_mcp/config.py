import tomllib
from pathlib import Path
from typing import Any

def load_config(config_path: str) -> dict[str, Any]:
    """Loads and parses the configuration from a TOML file.

    Args:
        config_path: The path to the TOML configuration file.

    Returns:
        A dictionary containing the parsed configuration.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with path.open("rb") as f:
        return tomllib.load(f)
