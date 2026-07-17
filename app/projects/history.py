from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, MutableMapping

from app.models.schedule import Schedule
from app.services.contracts import PlanningResult


SCHEDULE_HISTORY_STATE_KEY = "project_schedule_history"
PROJECT_METADATA_STATE_KEY = "active_project_metadata"


def _schedule_signature(schedule: Schedule) -> str:
    return f"{schedule.schedule_id}:{schedule.created_at_utc.isoformat()}"


def build_schedule_history_entry(
    result: PlanningResult,
    *,
    event_type: str,
    previous_schedule: Schedule | None = None,
) -> dict[str, Any]:
    """Buduje serializowalny wpis historii jednej wersji harmonogramu."""

    current_ids = {
        entry.opportunity_id for entry in result.schedule.active_entries
    }
    previous_ids = (
        {
            entry.opportunity_id
            for entry in previous_schedule.active_entries
        }
        if previous_schedule is not None
        else set()
    )
    return {
        "history_id": (
            f"HISTORY-{result.schedule.schedule_id}-"
            f"{result.schedule.created_at_utc.strftime('%Y%m%dT%H%M%S')}"
        ),
        "event_type": event_type.strip().upper(),
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "schedule_signature": _schedule_signature(result.schedule),
        "schedule": result.schedule.model_dump(mode="json"),
        "algorithm": result.options.algorithm.value,
        "options": {
            key: (
                value.value if hasattr(value, "value") else value
            )
            for key, value in vars(result.options).items()
        },
        "solver_status": result.solver_status,
        "wall_clock_runtime_s": result.wall_clock_runtime_s,
        "objective_value": result.objective_value,
        "fully_satisfied_requests": result.fully_satisfied_requests,
        "total_acquisitions": result.total_acquisitions,
        "previous_schedule_id": (
            previous_schedule.schedule_id
            if previous_schedule is not None
            else None
        ),
        "added_opportunity_ids": sorted(current_ids - previous_ids),
        "removed_opportunity_ids": sorted(previous_ids - current_ids),
    }


def record_schedule_history(
    state: MutableMapping[str, Any],
    result: PlanningResult,
    *,
    event_type: str,
    previous_schedule: Schedule | None = None,
) -> None:
    """Dopisuje wersję harmonogramu bez tworzenia duplikatów."""

    history = list(state.get(SCHEDULE_HISTORY_STATE_KEY, ()))
    entry = build_schedule_history_entry(
        result,
        event_type=event_type,
        previous_schedule=previous_schedule,
    )
    signature = entry["schedule_signature"]
    history = [
        item
        for item in history
        if item.get("schedule_signature") != signature
    ]
    history.append(entry)
    history.sort(key=lambda item: item.get("recorded_at_utc", ""))
    state[SCHEDULE_HISTORY_STATE_KEY] = history


__all__ = [
    "PROJECT_METADATA_STATE_KEY",
    "SCHEDULE_HISTORY_STATE_KEY",
    "build_schedule_history_entry",
    "record_schedule_history",
]
