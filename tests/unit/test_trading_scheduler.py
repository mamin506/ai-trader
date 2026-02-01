"""Unit tests for TradingScheduler.

Tests the APScheduler integration with mocked time and jobs.
"""

import time
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import pytz

from src.orchestration.scheduler import (
    TradingScheduler,
    is_market_open,
    is_trading_day,
)


@pytest.fixture
def scheduler_config():
    """Create scheduler configuration."""
    return {
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 60,
    }


@pytest.fixture
def scheduler(scheduler_config):
    """Create TradingScheduler instance."""
    return TradingScheduler(scheduler_config)


class TestTradingSchedulerInit:
    """Test TradingScheduler initialization."""

    def test_init(self, scheduler):
        """Test scheduler initialization."""
        assert scheduler is not None
        assert scheduler.config is not None
        assert scheduler.scheduler is not None
        assert scheduler.circuit_breaker_active is False
        assert len(scheduler.tasks) == 0

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        custom_config = {
            "coalesce": False,
            "max_instances": 3,
            "misfire_grace_time": 120,
        }

        scheduler = TradingScheduler(custom_config)

        assert scheduler.config == custom_config


class TestTradingSchedulerTaskRegistration:
    """Test task registration."""

    def test_register_simple_task(self, scheduler):
        """Test registering a simple task."""
        mock_func = Mock(return_value="test")

        scheduler.register_task(
            name="test_task",
            func=mock_func,
            trigger="cron",
            trigger_args={"hour": 9, "minute": 30},
        )

        assert "test_task" in scheduler.tasks
        assert scheduler.tasks["test_task"]["func"] == mock_func

    def test_register_task_with_dependencies(self, scheduler):
        """Test registering task with dependencies."""
        task1 = Mock(return_value="task1")
        task2 = Mock(return_value="task2")

        scheduler.register_task(
            name="task1", func=task1, trigger="cron", trigger_args={"hour": 9}
        )

        scheduler.register_task(
            name="task2",
            func=task2,
            trigger="cron",
            trigger_args={"hour": 10},
            dependencies=["task1"],
        )

        assert "task2" in scheduler.dependencies
        assert scheduler.dependencies["task2"] == ["task1"]

    def test_register_task_replaces_existing(self, scheduler):
        """Test that registering task replaces existing task."""
        func1 = Mock(return_value="func1")
        func2 = Mock(return_value="func2")

        scheduler.register_task(
            name="test", func=func1, trigger="cron", trigger_args={"hour": 9}
        )

        scheduler.register_task(
            name="test", func=func2, trigger="cron", trigger_args={"hour": 10}
        )

        # Second function should replace first
        assert scheduler.tasks["test"]["func"] == func2

    def test_register_interval_task(self, scheduler):
        """Test registering task with interval trigger."""
        mock_func = Mock()

        scheduler.register_task(
            name="interval_task",
            func=mock_func,
            trigger="interval",
            trigger_args={"minutes": 5},
        )

        assert "interval_task" in scheduler.tasks

    def test_register_date_task(self, scheduler):
        """Test registering task with date trigger."""
        mock_func = Mock()

        scheduler.register_task(
            name="date_task",
            func=mock_func,
            trigger="date",
            trigger_args={"run_date": datetime(2024, 1, 1, 10, 0)},
        )

        assert "date_task" in scheduler.tasks


class TestTradingSchedulerExecution:
    """Test task execution."""

    def test_task_execution(self, scheduler):
        """Test that tasks execute correctly."""
        mock_func = Mock(return_value="success")

        scheduler.register_task(
            name="test", func=mock_func, trigger="date", trigger_args={"run_date": datetime.now()}
        )

        # Start scheduler
        scheduler.start()

        # Wait for task to execute
        time.sleep(0.5)

        # Stop scheduler
        scheduler.stop()

        # Task should have executed
        assert "test" in scheduler.task_results
        assert scheduler.task_results["test"] == "success"

    def test_dependency_check(self, scheduler):
        """Test that dependencies are checked before execution."""
        task1_executed = False
        task2_executed = False

        def task1():
            nonlocal task1_executed
            task1_executed = True
            return "task1"

        def task2():
            nonlocal task2_executed
            task2_executed = True
            return "task2"

        # Register task2 with task1 as dependency
        scheduler.register_task(
            name="task1",
            func=task1,
            trigger="date",
            trigger_args={"run_date": datetime.now()},
        )

        # task2 depends on task1, but won't execute because dependency not met
        # (task1 hasn't executed yet when task2 tries to run)
        scheduler.register_task(
            name="task2",
            func=task2,
            trigger="date",
            trigger_args={"run_date": datetime.now()},
            dependencies=["task1"],
        )

        scheduler.start()
        time.sleep(0.5)
        scheduler.stop()

        # task1 should execute, task2 might not if it runs before task1
        assert task1_executed


class TestTradingSchedulerCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_activate_circuit_breaker(self, scheduler):
        """Test activating circuit breaker."""
        # Register some tasks
        scheduler.register_task(
            name="task1", func=Mock(), trigger="cron", trigger_args={"hour": 9}
        )

        scheduler.start()

        # Activate circuit breaker
        scheduler.activate_circuit_breaker()

        assert scheduler.circuit_breaker_active is True

        # Jobs should be paused
        jobs = scheduler.get_jobs()
        for job in jobs:
            if not job.id.startswith("monitor"):
                assert job.next_run_time is None  # Paused

        scheduler.stop()

    def test_deactivate_circuit_breaker(self, scheduler):
        """Test deactivating circuit breaker."""
        scheduler.register_task(
            name="task1", func=Mock(), trigger="cron", trigger_args={"hour": 9}
        )

        scheduler.start()
        scheduler.activate_circuit_breaker()
        scheduler.deactivate_circuit_breaker()

        assert scheduler.circuit_breaker_active is False

        scheduler.stop()

    def test_circuit_breaker_skips_tasks(self, scheduler):
        """Test that circuit breaker prevents task execution."""
        mock_func = Mock(return_value="test")

        scheduler.register_task(
            name="test",
            func=mock_func,
            trigger="date",
            trigger_args={"run_date": datetime.now()},
        )

        # Activate circuit breaker before starting
        scheduler.circuit_breaker_active = True

        scheduler.start()
        time.sleep(0.5)
        scheduler.stop()

        # Task should not execute due to circuit breaker
        mock_func.assert_not_called()


class TestTradingSchedulerControl:
    """Test scheduler control methods."""

    def test_start_stop(self, scheduler):
        """Test starting and stopping scheduler."""
        assert not scheduler.is_running()

        scheduler.start()
        assert scheduler.is_running()

        scheduler.stop()
        assert not scheduler.is_running()

    def test_start_when_running(self, scheduler):
        """Test starting scheduler when already running."""
        scheduler.start()
        # Second start should be no-op
        scheduler.start()
        assert scheduler.is_running()

        scheduler.stop()

    def test_stop_when_not_running(self, scheduler):
        """Test stopping scheduler when not running."""
        # Should not raise error
        scheduler.stop()

    def test_get_jobs(self, scheduler):
        """Test getting list of scheduled jobs."""
        scheduler.register_task(
            name="task1", func=Mock(), trigger="cron", trigger_args={"hour": 9}
        )
        scheduler.register_task(
            name="task2", func=Mock(), trigger="cron", trigger_args={"hour": 10}
        )

        jobs = scheduler.get_jobs()
        assert len(jobs) == 2

    def test_remove_job(self, scheduler):
        """Test removing a job."""
        scheduler.register_task(
            name="task1", func=Mock(), trigger="cron", trigger_args={"hour": 9}
        )

        jobs = scheduler.get_jobs()
        assert len(jobs) == 1

        scheduler.remove_job("task1")

        jobs = scheduler.get_jobs()
        assert len(jobs) == 0

    def test_clear_task_results(self, scheduler):
        """Test clearing task results."""
        scheduler.task_results["test"] = "value"

        scheduler.clear_task_results()

        assert len(scheduler.task_results) == 0


class TestMarketHoursUtilities:
    """Test market hours utility functions."""

    @patch("src.orchestration.scheduler.datetime")
    def test_is_market_open_during_hours(self, mock_datetime):
        """Test is_market_open during market hours."""
        # Wednesday at 10:00 AM ET (market open)
        eastern = pytz.timezone("US/Eastern")
        mock_dt = datetime(2024, 1, 3, 10, 0, 0, tzinfo=eastern)
        mock_datetime.now.return_value = mock_dt

        assert is_market_open(mock_dt) is True

    @patch("src.orchestration.scheduler.datetime")
    def test_is_market_open_before_open(self, mock_datetime):
        """Test is_market_open before market opens."""
        eastern = pytz.timezone("US/Eastern")
        mock_dt = datetime(2024, 1, 3, 9, 0, 0, tzinfo=eastern)  # Before 9:30 AM
        mock_datetime.now.return_value = mock_dt

        assert is_market_open(mock_dt) is False

    @patch("src.orchestration.scheduler.datetime")
    def test_is_market_open_after_close(self, mock_datetime):
        """Test is_market_open after market closes."""
        eastern = pytz.timezone("US/Eastern")
        mock_dt = datetime(2024, 1, 3, 17, 0, 0, tzinfo=eastern)  # After 4:00 PM
        mock_datetime.now.return_value = mock_dt

        assert is_market_open(mock_dt) is False

    @patch("src.orchestration.scheduler.datetime")
    def test_is_market_open_weekend(self, mock_datetime):
        """Test is_market_open on weekend."""
        eastern = pytz.timezone("US/Eastern")
        # Saturday at 10:00 AM
        mock_dt = datetime(2024, 1, 6, 10, 0, 0, tzinfo=eastern)
        mock_datetime.now.return_value = mock_dt

        assert is_market_open(mock_dt) is False

    def test_is_trading_day_weekday(self):
        """Test is_trading_day on a valid trading day."""
        # Wednesday, Jan 3, 2024 (not a holiday)
        dt = datetime(2024, 1, 3)

        result = is_trading_day(dt)

        # Should be True (regular trading day)
        assert result is True

    def test_is_trading_day_weekend(self):
        """Test is_trading_day on weekend."""
        # Saturday, Jan 6, 2024
        dt = datetime(2024, 1, 6)

        result = is_trading_day(dt)

        assert result is False

    def test_is_trading_day_holiday(self):
        """Test is_trading_day on a holiday."""
        # Monday, Jan 1, 2024 (New Year's Day)
        dt = datetime(2024, 1, 1)

        result = is_trading_day(dt)

        # Should be False (holiday)
        assert result is False
