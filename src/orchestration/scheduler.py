"""Trading Scheduler - APScheduler integration for daily trading workflows.

This module provides scheduling infrastructure for paper trading with:
- Market hours awareness (NYSE calendar)
- Task registration and dependency management
- Error handling and circuit breakers
- Timezone-aware scheduling (US/Eastern)
"""

import logging
from datetime import datetime, time
from typing import Callable, Dict, List, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from src.utils.logging import get_logger

logger = get_logger(__name__)

# US/Eastern timezone for market hours
EASTERN_TZ = pytz.timezone("US/Eastern")


class TradingScheduler:
    """APScheduler wrapper for trading workflows.

    Manages scheduled tasks for paper trading with market hours awareness,
    task dependencies, and error handling.

    Example:
        >>> scheduler = TradingScheduler(config)
        >>> scheduler.register_task(
        ...     name="market_open",
        ...     func=health_check,
        ...     trigger="cron",
        ...     trigger_args={"hour": 9, "minute": 30},
        ... )
        >>> scheduler.start()
    """

    def __init__(self, config: dict):
        """Initialize trading scheduler.

        Args:
            config: Configuration dictionary with scheduler settings
                - timezone: Timezone for scheduling (default: US/Eastern)
                - max_instances: Max concurrent job instances (default: 1)
                - coalesce: Combine missed jobs (default: True)
        """
        self.config = config
        self.timezone = EASTERN_TZ

        # Create APScheduler instance
        self.scheduler = BackgroundScheduler(
            timezone=self.timezone,
            job_defaults={
                "coalesce": config.get("coalesce", True),
                "max_instances": config.get("max_instances", 1),
                "misfire_grace_time": config.get("misfire_grace_time", 60),
            },
        )

        # Task registry and dependencies
        self.tasks: Dict[str, dict] = {}
        self.dependencies: Dict[str, List[str]] = {}
        self.task_results: Dict[str, any] = {}
        self.circuit_breaker_active = False

        # Add event listeners
        self.scheduler.add_listener(
            self._on_job_executed, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

        logger.info(
            "TradingScheduler initialized (timezone: %s)", self.timezone
        )

    def register_task(
        self,
        name: str,
        func: Callable,
        trigger: str,
        trigger_args: dict,
        dependencies: Optional[List[str]] = None,
    ):
        """Register a scheduled task with optional dependencies.

        Args:
            name: Unique task identifier
            func: Function to execute
            trigger: Trigger type ('cron', 'interval', 'date')
            trigger_args: Arguments for the trigger
            dependencies: List of task names that must complete first

        Example:
            >>> scheduler.register_task(
            ...     name="rebalance",
            ...     func=rebalance_portfolio,
            ...     trigger="cron",
            ...     trigger_args={"hour": 15, "minute": 45},
            ...     dependencies=["market_open"],
            ... )
        """
        if name in self.tasks:
            logger.warning("Task '%s' already registered, replacing", name)

        # Store task metadata
        self.tasks[name] = {
            "func": func,
            "trigger": trigger,
            "trigger_args": trigger_args,
        }

        if dependencies:
            self.dependencies[name] = dependencies

        # Create trigger
        trigger_obj = self._create_trigger(trigger, trigger_args)

        # Wrap function to check dependencies
        wrapped_func = self._wrap_with_dependencies(name, func)

        # Add job to scheduler
        job = self.scheduler.add_job(
            func=wrapped_func,
            trigger=trigger_obj,
            id=name,
            name=name,
            replace_existing=True,
        )

        # Get next run time safely
        try:
            next_run = job.next_run_time if hasattr(job, 'next_run_time') else "N/A"
        except AttributeError:
            next_run = "N/A"

        logger.info(
            "Registered task '%s' with trigger %s (next run: %s)",
            name,
            trigger,
            next_run,
        )

    def _create_trigger(self, trigger_type: str, args: dict):
        """Create APScheduler trigger from type and arguments.

        Args:
            trigger_type: 'cron', 'interval', or 'date'
            args: Trigger-specific arguments

        Returns:
            APScheduler trigger object
        """
        if trigger_type == "cron":
            return CronTrigger(timezone=self.timezone, **args)
        elif trigger_type == "interval":
            return IntervalTrigger(**args)
        elif trigger_type == "date":
            return DateTrigger(**args)
        else:
            raise ValueError(f"Unknown trigger type: {trigger_type}")

    def _wrap_with_dependencies(
        self, task_name: str, func: Callable
    ) -> Callable:
        """Wrap function to check dependencies before execution.

        Args:
            task_name: Name of the task
            func: Function to wrap

        Returns:
            Wrapped function that checks dependencies
        """

        def wrapped():
            # Check circuit breaker
            if self.circuit_breaker_active:
                logger.warning(
                    "Circuit breaker active, skipping task '%s'", task_name
                )
                return

            # Check dependencies
            if task_name in self.dependencies:
                for dep in self.dependencies[task_name]:
                    if dep not in self.task_results:
                        logger.warning(
                            "Dependency '%s' not completed, skipping '%s'",
                            dep,
                            task_name,
                        )
                        return

            # Execute task
            try:
                logger.info("Executing task '%s'", task_name)
                result = func()
                self.task_results[task_name] = result
                logger.info("Task '%s' completed successfully", task_name)
                return result

            except Exception as e:
                logger.error(
                    "Task '%s' failed: %s", task_name, e, exc_info=True
                )
                # Activate circuit breaker on critical errors
                if self._is_critical_error(e):
                    self.activate_circuit_breaker()
                raise

        return wrapped

    def _is_critical_error(self, error: Exception) -> bool:
        """Check if error should trigger circuit breaker.

        Args:
            error: Exception that occurred

        Returns:
            True if error is critical
        """
        # Import here to avoid circular dependency
        from src.utils.exceptions import (
            BrokerConnectionError,
            CircuitBreakerError,
        )

        critical_errors = (
            BrokerConnectionError,
            CircuitBreakerError,
        )

        return isinstance(error, critical_errors)

    def activate_circuit_breaker(self):
        """Activate circuit breaker to stop all trading.

        This prevents further order execution when critical errors occur.
        """
        logger.error("CIRCUIT BREAKER ACTIVATED - Stopping all trading tasks")
        self.circuit_breaker_active = True

        # Pause all jobs except monitoring
        for job in self.scheduler.get_jobs():
            if not job.id.startswith("monitor"):
                job.pause()
                logger.info("Paused job '%s'", job.id)

    def deactivate_circuit_breaker(self):
        """Deactivate circuit breaker and resume normal operations."""
        logger.info("Circuit breaker deactivated - Resuming normal operations")
        self.circuit_breaker_active = False

        # Resume all jobs
        for job in self.scheduler.get_jobs():
            try:
                is_paused = (hasattr(job, 'next_run_time') and job.next_run_time is None)
            except AttributeError:
                is_paused = False

            if is_paused:  # Job is paused
                job.resume()
                logger.info("Resumed job '%s'", job.id)

    def _on_job_executed(self, event):
        """Event listener for job execution/errors.

        Args:
            event: APScheduler event object
        """
        job_id = event.job_id

        if event.exception:
            logger.error(
                "Job '%s' raised exception: %s",
                job_id,
                event.exception,
                exc_info=event.exception,
            )
        else:
            logger.debug("Job '%s' executed successfully", job_id)

    def start(self):
        """Start the scheduler (non-blocking).

        The scheduler runs in the background and executes jobs according
        to their schedules.
        """
        if self.scheduler.running:
            logger.warning("Scheduler already running")
            return

        self.scheduler.start()
        logger.info("Scheduler started successfully")

        # Log scheduled jobs
        jobs = self.scheduler.get_jobs()
        logger.info("Scheduled jobs (%d):", len(jobs))
        for job in jobs:
            try:
                next_run = job.next_run_time if hasattr(job, 'next_run_time') else "N/A"
            except AttributeError:
                next_run = "N/A"
            logger.info(
                "  - %s: next run at %s", job.id, next_run
            )

    def stop(self):
        """Stop the scheduler gracefully.

        Waits for running jobs to complete before shutting down.
        """
        if not self.scheduler.running:
            logger.warning("Scheduler not running")
            return

        logger.info("Shutting down scheduler...")
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")

    def is_running(self) -> bool:
        """Check if scheduler is running.

        Returns:
            True if scheduler is active
        """
        return self.scheduler.running

    def get_jobs(self) -> list:
        """Get list of scheduled jobs.

        Returns:
            List of APScheduler Job objects
        """
        return self.scheduler.get_jobs()

    def remove_job(self, job_id: str):
        """Remove a scheduled job.

        Args:
            job_id: Job identifier
        """
        self.scheduler.remove_job(job_id)
        logger.info("Removed job '%s'", job_id)

    def clear_task_results(self):
        """Clear task execution results.

        Useful for testing or resetting state between trading days.
        """
        self.task_results.clear()
        logger.debug("Cleared task results")


def is_market_open(dt: Optional[datetime] = None) -> bool:
    """Check if NYSE market is currently open.

    Args:
        dt: Datetime to check (default: now in US/Eastern)

    Returns:
        True if market is open

    Example:
        >>> if is_market_open():
        ...     execute_trade()
    """
    if dt is None:
        dt = datetime.now(EASTERN_TZ)
    elif dt.tzinfo is None:
        dt = EASTERN_TZ.localize(dt)

    # Check if it's a weekday
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    # Check if within market hours (9:30 AM - 4:00 PM ET)
    market_open = time(9, 30)
    market_close = time(16, 0)
    current_time = dt.time()

    return market_open <= current_time <= market_close


def is_trading_day(dt: Optional[datetime] = None) -> bool:
    """Check if date is a valid NYSE trading day.

    Uses exchange_calendars to check for holidays.

    Args:
        dt: Date to check (default: today)

    Returns:
        True if it's a trading day

    Example:
        >>> if is_trading_day():
        ...     schedule_rebalance()
    """
    import exchange_calendars as xcals

    if dt is None:
        dt = datetime.now(EASTERN_TZ)

    nyse = xcals.get_calendar("XNYS")

    # Convert to pandas Timestamp
    import pandas as pd

    ts = pd.Timestamp(dt)

    return nyse.is_session(ts)
