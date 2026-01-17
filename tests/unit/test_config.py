"""Unit tests for configuration management."""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.utils.config import Config


class TestConfig:
    """Test cases for Config class."""

    def test_from_file_valid_yaml(self, tmp_path: Path) -> None:
        """Test loading valid YAML configuration file."""
        config_file = tmp_path / "test_config.yaml"
        config_data = {
            "project": {"name": "test", "version": "1.0"},
            "logging": {"level": "DEBUG"},
        }
        config_file.write_text(yaml.dump(config_data))

        config = Config.from_file(config_file)
        assert config.get("project.name") == "test"
        assert config.get("logging.level") == "DEBUG"

    def test_from_file_empty_yaml(self, tmp_path: Path) -> None:
        """Test loading empty YAML file."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        config = Config.from_file(config_file)
        assert config.to_dict() == {}

    def test_from_file_not_found(self) -> None:
        """Test loading non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            Config.from_file("nonexistent.yaml")

    def test_get_nested_key(self) -> None:
        """Test getting nested configuration values."""
        config_dict = {
            "database": {"host": "localhost", "port": 5432},
            "api": {"timeout": 30},
        }
        config = Config(config_dict)

        assert config.get("database.host") == "localhost"
        assert config.get("database.port") == 5432
        assert config.get("api.timeout") == 30

    def test_get_default_value(self) -> None:
        """Test getting default value for missing key."""
        config = Config({"existing": "value"})

        assert config.get("missing.key", "default") == "default"
        assert config.get("existing", "default") == "value"

    def test_get_none_for_missing_key(self) -> None:
        """Test getting None for missing key without default."""
        config = Config({"existing": "value"})

        assert config.get("missing.key") is None

    def test_bracket_notation(self) -> None:
        """Test accessing config with bracket notation."""
        config = Config({"key": "value", "nested": {"key": "nested_value"}})

        assert config["key"] == "value"
        assert config["nested.key"] == "nested_value"

    def test_bracket_notation_key_error(self) -> None:
        """Test bracket notation raises KeyError for missing key."""
        config = Config({"existing": "value"})

        with pytest.raises(KeyError, match="Configuration key not found"):
            _ = config["missing.key"]

    def test_to_dict(self) -> None:
        """Test converting config to dictionary."""
        config_dict = {"key1": "value1", "key2": {"nested": "value2"}}
        config = Config(config_dict)

        result = config.to_dict()
        assert result == config_dict
        # Ensure it's a copy, not the original
        assert result is not config._config

    def test_get_with_non_dict_intermediate(self) -> None:
        """Test getting nested key when intermediate value is not a dict."""
        config = Config({"key": "string_value"})

        # Trying to access "key.nested" should return default
        # because "key" is a string, not a dict
        assert config.get("key.nested", "default") == "default"


def test_load_default_config() -> None:
    """Integration test: Load the actual default.yaml config."""
    config_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"

    if config_path.exists():
        config = Config.from_file(config_path)
        # Verify expected keys exist
        assert config.get("project.name") is not None
        assert config.get("logging.level") is not None
