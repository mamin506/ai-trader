"""Configuration management for AI Trader.

This module provides simple YAML configuration loading and access.
"""

from pathlib import Path
from typing import Any

import yaml


class Config:
    """Simple configuration loader and accessor.

    Loads YAML configuration files and provides dict-like access to settings.

    Example:
        >>> config = Config.from_file("config/default.yaml")
        >>> log_level = config.get("logging.level", "INFO")
    """

    def __init__(self, config_dict: dict[str, Any]) -> None:
        """Initialize with configuration dictionary.

        Args:
            config_dict: Configuration data as nested dictionary
        """
        self._config = config_dict

    @classmethod
    def from_file(cls, filepath: str | Path) -> "Config":
        """Load configuration from YAML file.

        Args:
            filepath: Path to YAML configuration file

        Returns:
            Config instance with loaded configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {filepath}")

        with open(path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)

        if config_dict is None:
            config_dict = {}

        return cls(config_dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Supports nested keys using dot notation (e.g., "logging.level").

        Args:
            key: Configuration key (supports dot notation for nested keys)
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            >>> config.get("database.path")
            'data/trader.db'
            >>> config.get("missing.key", "fallback")
            'fallback'
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def __getitem__(self, key: str) -> Any:
        """Get configuration value using bracket notation.

        Args:
            key: Configuration key (supports dot notation)

        Returns:
            Configuration value

        Raises:
            KeyError: If key not found
        """
        value = self.get(key)
        if value is None:
            raise KeyError(f"Configuration key not found: {key}")
        return value

    def to_dict(self) -> dict[str, Any]:
        """Get the full configuration as dictionary.

        Returns:
            Complete configuration dictionary
        """
        return self._config.copy()


def load_config(filepath: str | Path = None) -> Config:
    """Helper function to load configuration.

    Args:
        filepath: Path to YAML configuration file. If None, uses default path.

    Returns:
        Config instance
    """
    if filepath is None:
        # Use absolute path to default config relative to project root
        root_dir = Path(__file__).parent.parent.parent
        filepath = root_dir / "config" / "default.yaml"
    return Config.from_file(filepath)
