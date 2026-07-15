from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.models.enums import RequestStatus, SensorType
from app.models.opportunity import AcquisitionOpportunity
from app.models.request import ObservationRequest
from app.models.schedule import Schedule, ScheduleEntry
from app.services.disruption_service import (
    CloudCoverUpdate,
    DisruptionPlan,
    SatelliteOutage,
    UrgentRequestPackage,
)
from app.services.scenario_service import LoadedScenario


DEFAULT_WEATHER_REASON = (
    "Zachmurzenie przekroczyło limit zlecenia optycznego."
)


def build_example_disruption_plan(
    *,
    scenario: LoadedScenario,
    previous_schedule: Schedule,
    replan_at_utc: datetime,
    freeze_duration: timedelta = timedelta(hours=2),
) -> DisruptionPlan:
    """Buduje deterministyczny plan awarii, pogody i pilnego zadania."""

    replan_at = _normalize_utc(replan_at_utc)

    if freeze_duration <= timedelta(0):
        raise ValueError("freeze_duration musi być większe od zera")

    frozen_until = min(
        replan_at + freeze_duration,
        scenario.request_set.horizon_end_utc,
    )

    request_by_id = {
        request.request_id: request
        for request in scenario.request_set.requests
    }
    opportunity_by_id = {
        opportunity.opportunity_id: opportunity
        for opportunity in scenario.opportunity_set.opportunities
    }

    future_entries = [
        entry
        for entry in previous_schedule.active_entries
        if entry.start_utc >= frozen_until
    ]

    if not future_entries:
        raise ValueError(
            "Poprzedni harmonogram nie zawiera akwizycji po oknie zamrożonym"
        )

    outage_satellite_id = _select_outage_satellite(
        future_entries=future_entries,
        request_by_id=request_by_id,
    )

    weather_entry = _select_weather_entry(
        future_entries=future_entries,
        request_by_id=request_by_id,
        outage_satellite_id=outage_satellite_id,
    )

    urgent_source_entry = _select_urgent_source_entry(
        future_entries=future_entries,
        request_by_id=request_by_id,
        outage_satellite_id=outage_satellite_id,
    )

    urgent_package = _build_urgent_request_package(
        scenario=scenario,
        source_entry=urgent_source_entry,
        source_opportunity=opportunity_by_id[
            urgent_source_entry.opportunity_id
        ],
        source_request=request_by_id[
            urgent_source_entry.request_id
        ],
        frozen_until_utc=frozen_until,
    )

    timestamp = replan_at.strftime("%Y%m%dT%H%M%SZ")

    return DisruptionPlan(
        plan_id=f"DISRUPTION-{scenario.scenario_id}-{timestamp}",
        occurred_at_utc=replan_at,
        satellite_outages=(
            SatelliteOutage(
                satellite_id=outage_satellite_id,
                effective_from_utc=frozen_until,
                reason=(
                    f"Awaria {outage_satellite_id} po zakończeniu "
                    "operacyjnego okna zamrożonego."
                ),
            ),
        ),
        cloud_cover_updates=(
            CloudCoverUpdate(
                opportunity_id=weather_entry.opportunity_id,
                cloud_cover=1.0,
                reason=DEFAULT_WEATHER_REASON,
            ),
        ),
        urgent_requests=(urgent_package,),
        notes=(
            "Scenariusz demonstracyjny: awaria satelity, pogorszenie "
            "pogody i nowe obowiązkowe zlecenie SAR."
        ),
    )


def _select_outage_satellite(
    *,
    future_entries: list[ScheduleEntry],
    request_by_id: dict[str, ObservationRequest],
) -> str:
    entries_by_satellite: dict[str, list[ScheduleEntry]] = defaultdict(list)

    for entry in future_entries:
        entries_by_satellite[entry.satellite_id].append(entry)

    eligible: list[tuple[int, str]] = []

    for satellite_id, entries in entries_by_satellite.items():
        contains_mandatory = any(
            request_by_id[entry.request_id].is_mandatory
            for entry in entries
        )

        if not contains_mandatory:
            eligible.append((len(entries), satellite_id))

    if not eligible:
        raise ValueError(
            "Nie znaleziono satelity, którego awaria nie narusza "
            "przyszłych zleceń obowiązkowych"
        )

    eligible.sort(key=lambda item: (-item[0], item[1]))
    return eligible[0][1]


def _select_weather_entry(
    *,
    future_entries: list[ScheduleEntry],
    request_by_id: dict[str, ObservationRequest],
    outage_satellite_id: str,
) -> ScheduleEntry:
    candidates = [
        entry
        for entry in future_entries
        if entry.sensor_type == SensorType.OPTICAL
        and entry.satellite_id != outage_satellite_id
        and not request_by_id[entry.request_id].is_mandatory
    ]

    if not candidates:
        raise ValueError(
            "Nie znaleziono przyszłej nieobowiązkowej akwizycji optycznej"
        )

    return min(
        candidates,
        key=lambda entry: (entry.start_utc, entry.opportunity_id),
    )


def _select_urgent_source_entry(
    *,
    future_entries: list[ScheduleEntry],
    request_by_id: dict[str, ObservationRequest],
    outage_satellite_id: str,
) -> ScheduleEntry:
    candidates = [
        entry
        for entry in future_entries
        if entry.sensor_type == SensorType.SAR
        and entry.satellite_id != outage_satellite_id
        and not request_by_id[entry.request_id].is_mandatory
    ]

    if not candidates:
        raise ValueError(
            "Nie znaleziono przyszłej nieobowiązkowej akwizycji SAR"
        )

    return max(
        candidates,
        key=lambda entry: (
            entry.objective_contribution,
            -entry.start_utc.timestamp(),
            entry.opportunity_id,
        ),
    )


def _build_urgent_request_package(
    *,
    scenario: LoadedScenario,
    source_entry: ScheduleEntry,
    source_opportunity: AcquisitionOpportunity,
    source_request: ObservationRequest,
    frozen_until_utc: datetime,
) -> UrgentRequestPackage:
    request_id = _next_identifier(
        existing_ids={
            request.request_id
            for request in scenario.request_set.requests
        },
        prefix="REQ-URGENT-",
    )
    opportunity_id = _next_identifier(
        existing_ids={
            opportunity.opportunity_id
            for opportunity in scenario.opportunity_set.opportunities
        },
        prefix="OPP-URGENT-",
    )

    latest_end = min(
        scenario.request_set.horizon_end_utc,
        source_opportunity.end_utc + timedelta(hours=2),
    )

    request_data = source_request.model_dump()
    request_data.update(
        {
            "request_id": request_id,
            "name": "Pilne zlecenie kryzysowe SAR",
            "priority": 10,
            "earliest_start_utc": frozen_until_utc,
            "latest_end_utc": latest_end,
            "status": RequestStatus.ACTIVE,
            "is_mandatory": True,
            "external_reference": "DISRUPTION-URGENT",
            "notes": (
                "Zlecenie dodane operacyjnie podczas dynamicznego "
                "przeplanowania."
            ),
        }
    )
    urgent_request = ObservationRequest.model_validate(request_data)

    opportunity_data = source_opportunity.model_dump()
    opportunity_data.update(
        {
            "opportunity_id": opportunity_id,
            "request_id": request_id,
            "quality_score": 1.0,
            "coverage_ratio": max(
                source_opportunity.coverage_ratio,
                urgent_request.minimum_coverage_ratio,
            ),
            "is_feasible": True,
            "infeasibility_reasons": [],
            "notes": (
                "Syntetyczna okazja pilnego zlecenia, celowo kolidująca "
                f"z {source_entry.opportunity_id}."
            ),
        }
    )
    urgent_opportunity = AcquisitionOpportunity.model_validate(
        opportunity_data
    )

    return UrgentRequestPackage(
        request=urgent_request,
        opportunities=(urgent_opportunity,),
    )


def _next_identifier(*, existing_ids: set[str], prefix: str) -> str:
    index = 1

    while True:
        candidate = f"{prefix}{index:03d}"

        if candidate not in existing_ids:
            return candidate

        index += 1


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("replan_at_utc musi zawierać strefę czasową")

    return value.astimezone(timezone.utc)
