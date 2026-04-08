from __future__ import annotations

"""Prefect orchestration skeleton for durable execution migration.

This module is optional at runtime. It is imported only when Prefect is installed
and ORCHESTRATION_BACKEND=prefect is configured.
"""

from collections.abc import Callable

try:
    from prefect import flow, task
except Exception:  # pragma: no cover
    flow = None
    task = None


def build_prefect_flows(
    monitor_fn: Callable[[], None],
    research_fn: Callable[[], None],
    validate_fn: Callable[[], None],
    release_fn: Callable[[], None],
    rollback_fn: Callable[[], None],
) -> dict[str, object]:
    if flow is None or task is None:
        return {}

    @task(retries=2, retry_delay_seconds=1, timeout_seconds=15)
    def monitor_task() -> None:
        monitor_fn()

    @task(retries=2, retry_delay_seconds=1, timeout_seconds=20)
    def research_task() -> None:
        research_fn()

    @task(retries=2, retry_delay_seconds=1, timeout_seconds=20)
    def validate_task() -> None:
        validate_fn()

    @task(retries=2, retry_delay_seconds=1, timeout_seconds=20)
    def release_task() -> None:
        release_fn()

    @task(retries=2, retry_delay_seconds=1, timeout_seconds=20)
    def rollback_task() -> None:
        rollback_fn()

    @flow(name="monitor_workflow")
    def monitor_workflow() -> None:
        monitor_task()

    @flow(name="research_workflow")
    def research_workflow() -> None:
        research_task()

    @flow(name="validate_workflow")
    def validate_workflow() -> None:
        validate_task()

    @flow(name="release_workflow")
    def release_workflow() -> None:
        release_task()

    @flow(name="rollback_workflow")
    def rollback_workflow() -> None:
        rollback_task()

    return {
        "monitor_workflow": monitor_workflow,
        "research_workflow": research_workflow,
        "validate_workflow": validate_workflow,
        "release_workflow": release_workflow,
        "rollback_workflow": rollback_workflow,
    }
