"""Configuration management for AI Trader.

This module provides simple YAML configuration loading and access.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


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


def load_alpaca_config(config_file: str | Path = None) -> tuple[Config, dict[str, str]]:
    """Load Alpaca configuration from YAML and environment variables.

    This function loads both the alpaca.yaml config file and the .env file
    containing API credentials. It's designed for Phase 2 paper trading.

    Args:
        config_file: Path to alpaca.yaml file. If None, uses default path.

    Returns:
        Tuple of (Config object, credentials dict)
        where credentials dict contains:
            - api_key: Alpaca API key
            - secret_key: Alpaca secret key
            - base_url: Alpaca API base URL
            - data_url: Alpaca data API URL

    Raises:
        FileNotFoundError: If config file or .env not found
        ValueError: If required environment variables are missing

    Example:
        >>> config, creds = load_alpaca_config()
        >>> stop_loss = config.get("alpaca.risk_monitoring.stop_loss_pct")
        >>> api_key = creds["api_key"]
    """
    # Load environment variables from .env file
    root_dir = Path(__file__).parent.parent.parent
    env_file = root_dir / ".env"

    if not env_file.exists():
        raise FileNotFoundError(
            f".env file not found at {env_file}. "
            "Please copy .env.example to .env and fill in your credentials."
        )

    load_dotenv(env_file)

    # Load Alpaca YAML configuration
    if config_file is None:
        config_file = root_dir / "config" / "alpaca.yaml"

    config = Config.from_file(config_file)

    # Extract credentials from environment variables
    required_vars = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_BASE_URL", "ALPACA_DATA_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}. "
            "Please check your .env file."
        )

    credentials = {
        "api_key": os.getenv("ALPACA_API_KEY"),
        "secret_key": os.getenv("ALPACA_SECRET_KEY"),
        "base_url": os.getenv("ALPACA_BASE_URL"),
        "data_url": os.getenv("ALPACA_DATA_URL"),
    }

    return config, credentials
