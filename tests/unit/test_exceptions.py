"""Unit tests for custom exceptions."""

import pytest

from src.utils.exceptions import (
    AITraderError,
    ConfigurationError,
    DataError,
    DataProviderError,
    DataQualityError,
    StorageError,
)


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_configuration_error_inherits_from_aitrader_error(self) -> None:
        """Test ConfigurationError is a subclass of AITraderError."""
        assert issubclass(ConfigurationError, AITraderError)

    def test_data_error_inherits_from_aitrader_error(self) -> None:
        """Test DataError is a subclass of AITraderError."""
        assert issubclass(DataError, AITraderError)

    def test_data_provider_error_inherits_from_data_error(self) -> None:
        """Test DataProviderError is a subclass of DataError."""
        assert issubclass(DataProviderError, DataError)
        assert issubclass(DataProviderError, AITraderError)

    def test_data_quality_error_inherits_from_data_error(self) -> None:
        """Test DataQualityError is a subclass of DataError."""
        assert issubclass(DataQualityError, DataError)
        assert issubclass(DataQualityError, AITraderError)

    def test_storage_error_inherits_from_data_error(self) -> None:
        """Test StorageError is a subclass of DataError."""
        assert issubclass(StorageError, DataError)
        assert issubclass(StorageError, AITraderError)


class TestExceptionRaising:
    """Test raising and catching exceptions."""

    def test_raise_aitrader_error(self) -> None:
        """Test raising and catching AITraderError."""
        with pytest.raises(AITraderError, match="Base error"):
            raise AITraderError("Base error")

    def test_raise_configuration_error(self) -> None:
        """Test raising and catching ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Config missing"):
            raise ConfigurationError("Config missing")

    def test_raise_data_error(self) -> None:
        """Test raising and catching DataError."""
        with pytest.raises(DataError, match="Data error occurred"):
            raise DataError("Data error occurred")

    def test_raise_data_provider_error(self) -> None:
        """Test raising and catching DataProviderError."""
        with pytest.raises(DataProviderError, match="API failed"):
            raise DataProviderError("API failed")

    def test_raise_data_quality_error(self) -> None:
        """Test raising and catching DataQualityError."""
        with pytest.raises(DataQualityError, match="Invalid data"):
            raise DataQualityError("Invalid data")

    def test_raise_storage_error(self) -> None:
        """Test raising and catching StorageError."""
        with pytest.raises(StorageError, match="Database failed"):
            raise StorageError("Database failed")


class TestExceptionCatching:
    """Test catching exceptions at different levels."""

    def test_catch_data_provider_error_as_data_error(self) -> None:
        """Test DataProviderError can be caught as DataError."""
        with pytest.raises(DataError):
            raise DataProviderError("API failed")

    def test_catch_data_provider_error_as_aitrader_error(self) -> None:
        """Test DataProviderError can be caught as AITraderError."""
        with pytest.raises(AITraderError):
            raise DataProviderError("API failed")

    def test_catch_configuration_error_as_aitrader_error(self) -> None:
        """Test ConfigurationError can be caught as AITraderError."""
        with pytest.raises(AITraderError):
            raise ConfigurationError("Config missing")

    def test_catch_specific_exception(self) -> None:
        """Test catching specific exception type."""
        try:
            raise DataQualityError("Bad data")
        except DataQualityError as e:
            assert str(e) == "Bad data"
        except DataError:
            pytest.fail("Should have caught DataQualityError specifically")

    def test_exception_message_preserved(self) -> None:
        """Test exception message is preserved through inheritance."""
        error_msg = "Detailed error message"
        try:
            raise DataProviderError(error_msg)
        except AITraderError as e:
            assert str(e) == error_msg


class TestExceptionInheritance:
    """Test exception isinstance checks."""

    def test_data_provider_error_isinstance_checks(self) -> None:
        """Test isinstance for DataProviderError."""
        error = DataProviderError("test")
        assert isinstance(error, DataProviderError)
        assert isinstance(error, DataError)
        assert isinstance(error, AITraderError)
        assert isinstance(error, Exception)

    def test_configuration_error_isinstance_checks(self) -> None:
        """Test isinstance for ConfigurationError."""
        error = ConfigurationError("test")
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, AITraderError)
        assert isinstance(error, Exception)
        assert not isinstance(error, DataError)

    def test_storage_error_isinstance_checks(self) -> None:
        """Test isinstance for StorageError."""
        error = StorageError("test")
        assert isinstance(error, StorageError)
        assert isinstance(error, DataError)
        assert isinstance(error, AITraderError)
        assert not isinstance(error, ConfigurationError)
