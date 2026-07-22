from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol

from app.models.catalog import SystemCatalog
from app.models.downlink import DownlinkOpportunity
from app.models.downlink_set import DownlinkOpportunitySet
from app.models.opportunity import AcquisitionOpportunity
from app.models.schedule import (
    DownlinkScheduleEntry,
    MemoryTimelinePoint,
    SatelliteResourceSummary,
)


_RESOURCE_TOLERANCE_MB = 1e-3


class ResourcePlannerConfig(Protocol):
    memory_reserve_ratio: float
    enable_downlink_planning: bool
    require_full_downlink: bool
    allow_simultaneous_imaging_downlink: bool


@dataclass(frozen=True)
class ResourcePlanResult:
    feasible: bool
    downlink_entries: tuple[DownlinkScheduleEntry, ...]
    summaries: tuple[SatelliteResourceSummary, ...]
    memory_timeline: tuple[MemoryTimelinePoint, ...]
    rejection_reasons: tuple[str, ...] = ()


@dataclass
class _DataChunk:
    reference_id: str
    remaining_mb: float


@dataclass(frozen=True)
class _PlannedWindow:
    opportunity: DownlinkOpportunity
    planned_data_volume_mb: float


def _overlaps(
    first_start: datetime,
    first_end: datetime,
    second_start: datetime,
    second_end: datetime,
) -> bool:
    return first_start < second_end and second_start < first_end


def _window_conflicts_with_acquisition(
    window: DownlinkOpportunity,
    acquisitions: Iterable[AcquisitionOpportunity],
) -> bool:
    return any(
        acquisition.satellite_id == window.satellite_id
        and _overlaps(
            window.start_utc,
            window.end_utc,
            acquisition.start_utc,
            acquisition.end_utc,
        )
        for acquisition in acquisitions
    )


def _consume_chunks(
    chunks: deque[_DataChunk],
    amount_mb: float,
) -> tuple[float, tuple[str, ...]]:
    remaining = amount_mb
    consumed = 0.0
    references: list[str] = []
    while chunks and remaining > 1e-9:
        chunk = chunks[0]
        portion = min(chunk.remaining_mb, remaining)
        if portion > 1e-9 and chunk.reference_id not in references:
            references.append(chunk.reference_id)
        chunk.remaining_mb -= portion
        remaining -= portion
        consumed += portion
        if chunk.remaining_mb <= 1e-9:
            chunks.popleft()
    return consumed, tuple(references)


def _station_capacity_available(
    *,
    candidate: DownlinkOpportunity,
    selected_windows: list[DownlinkOpportunity],
    station_capacity: int,
) -> bool:
    overlapping = sum(
        existing.ground_station_id == candidate.ground_station_id
        and _overlaps(
            existing.start_utc,
            existing.end_utc,
            candidate.start_utc,
            candidate.end_utc,
        )
        for existing in selected_windows
    )
    return overlapping < station_capacity


def _build_result(
    *,
    catalog: SystemCatalog,
    acquisitions: list[AcquisitionOpportunity],
    planned_windows: list[_PlannedWindow],
    memory_reserve_ratio: float,
    require_full_downlink: bool,
    downlink_capacity_reserve_ratio: float,
    horizon_start_utc: datetime,
) -> ResourcePlanResult:
    acquisitions_by_satellite: dict[
        str,
        list[AcquisitionOpportunity],
    ] = defaultdict(list)
    for acquisition in acquisitions:
        acquisitions_by_satellite[acquisition.satellite_id].append(acquisition)

    windows_by_satellite: dict[str, list[_PlannedWindow]] = defaultdict(list)
    for planned in planned_windows:
        windows_by_satellite[planned.opportunity.satellite_id].append(planned)

    entries: list[DownlinkScheduleEntry] = []
    summaries: list[SatelliteResourceSummary] = []
    timeline: list[MemoryTimelinePoint] = []
    reasons: list[str] = []

    for satellite in sorted(catalog.satellites, key=lambda item: item.satellite_id):
        satellite_acquisitions = sorted(
            acquisitions_by_satellite.get(satellite.satellite_id, []),
            key=lambda item: (item.end_utc, item.opportunity_id),
        )
        satellite_windows = sorted(
            windows_by_satellite.get(satellite.satellite_id, []),
            key=lambda item: (
                item.opportunity.start_utc,
                item.opportunity.end_utc,
                item.opportunity.downlink_opportunity_id,
            ),
        )
        memory_limit = satellite.memory_capacity_mb * (1.0 - memory_reserve_ratio)
        chunks: deque[_DataChunk] = deque()
        if satellite.initial_memory_usage_mb > 1e-9:
            chunks.append(_DataChunk("INITIAL", satellite.initial_memory_usage_mb))
        current_memory = satellite.initial_memory_usage_mb
        peak_memory = current_memory
        acquired_data = 0.0
        downlinked_data = 0.0
        memory_feasible = (
            current_memory <= memory_limit + _RESOURCE_TOLERANCE_MB
        )

        timeline.append(
            MemoryTimelinePoint(
                satellite_id=satellite.satellite_id,
                timestamp_utc=horizon_start_utc,
                event_type="INITIAL",
                reference_id="INITIAL",
                delta_mb=0.0,
                memory_used_mb=current_memory,
                memory_limit_mb=memory_limit,
            )
        )

        events: list[tuple[datetime, int, str, object]] = []
        for acquisition in satellite_acquisitions:
            events.append((acquisition.end_utc, 0, "ACQUISITION", acquisition))
        for planned in satellite_windows:
            events.append((planned.opportunity.end_utc, 1, "DOWNLINK", planned))

        for timestamp, _, event_type, payload in sorted(
            events,
            key=lambda item: (
                item[0],
                item[1],
                str(getattr(item[3], "opportunity_id", "")),
            ),
        ):
            if event_type == "ACQUISITION":
                acquisition = payload
                assert isinstance(acquisition, AcquisitionOpportunity)
                chunks.append(
                    _DataChunk(
                        acquisition.opportunity_id,
                        acquisition.estimated_data_volume_mb,
                    )
                )
                current_memory += acquisition.estimated_data_volume_mb
                acquired_data += acquisition.estimated_data_volume_mb
                delta = acquisition.estimated_data_volume_mb
                reference_id = acquisition.opportunity_id
            else:
                planned = payload
                assert isinstance(planned, _PlannedWindow)
                available = sum(chunk.remaining_mb for chunk in chunks)
                requested = min(planned.planned_data_volume_mb, available)
                consumed, delivered_references = _consume_chunks(
                    chunks,
                    requested,
                )
                current_memory = max(0.0, current_memory - consumed)
                downlinked_data += consumed
                delta = -consumed
                reference_id = planned.opportunity.downlink_opportunity_id
                if consumed > 1e-9:
                    entries.append(
                        DownlinkScheduleEntry(
                            entry_id=(
                                "DOWNLINK-ENTRY-"
                                + planned.opportunity.downlink_opportunity_id
                                .removeprefix("DLO-")
                            ),
                            downlink_opportunity_id=(
                                planned.opportunity.downlink_opportunity_id
                            ),
                            satellite_id=planned.opportunity.satellite_id,
                            ground_station_id=(
                                planned.opportunity.ground_station_id
                            ),
                            start_utc=planned.opportunity.start_utc,
                            end_utc=planned.opportunity.end_utc,
                            planned_data_volume_mb=consumed,
                            capacity_mb=planned.opportunity.capacity_mb,
                            planning_capacity_mb=(
                                planned.opportunity.capacity_mb
                                * (1.0 - downlink_capacity_reserve_ratio)
                            ),
                            data_rate_mbps=planned.opportunity.data_rate_mbps,
                            station_capacity=(
                                catalog.get_ground_station(
                                    planned.opportunity.ground_station_id
                                ).max_simultaneous_contacts
                            ),
                            delivered_reference_ids=list(delivered_references),
                            notes="Plan transmisji danych pokładowych.",
                        )
                    )

            peak_memory = max(peak_memory, current_memory)
            if current_memory > memory_limit + _RESOURCE_TOLERANCE_MB:
                memory_feasible = False
            timeline.append(
                MemoryTimelinePoint(
                    satellite_id=satellite.satellite_id,
                    timestamp_utc=timestamp,
                    event_type=event_type,
                    reference_id=reference_id,
                    delta_mb=delta,
                    memory_used_mb=current_memory,
                    memory_limit_mb=memory_limit,
                )
            )

        delivery_complete = current_memory <= _RESOURCE_TOLERANCE_MB
        if not memory_feasible:
            reasons.append(
                f"{satellite.satellite_id}: przekroczono dynamiczny limit pamięci"
            )
        if require_full_downlink and not delivery_complete:
            reasons.append(
                f"{satellite.satellite_id}: dane pozostały w pamięci "
                "na końcu horyzontu"
            )

        summaries.append(
            SatelliteResourceSummary(
                satellite_id=satellite.satellite_id,
                memory_capacity_mb=satellite.memory_capacity_mb,
                planning_memory_limit_mb=memory_limit,
                initial_memory_usage_mb=satellite.initial_memory_usage_mb,
                peak_memory_usage_mb=peak_memory,
                final_memory_usage_mb=current_memory,
                acquired_data_mb=acquired_data,
                downlinked_data_mb=downlinked_data,
                selected_downlink_windows=sum(
                    entry.satellite_id == satellite.satellite_id for entry in entries
                ),
                memory_feasible=memory_feasible,
                delivery_complete=delivery_complete,
            )
        )

    feasible = not reasons
    return ResourcePlanResult(
        feasible=feasible,
        downlink_entries=tuple(
            sorted(
                entries,
                key=lambda item: (
                    item.start_utc,
                    item.ground_station_id,
                    item.satellite_id,
                    item.entry_id,
                ),
            )
        ),
        summaries=tuple(summaries),
        memory_timeline=tuple(
            sorted(
                timeline,
                key=lambda item: (
                    item.timestamp_utc,
                    item.satellite_id,
                    item.event_type,
                    item.reference_id,
                ),
            )
        ),
        rejection_reasons=tuple(reasons),
    )


def allocate_downlinks_greedily(
    *,
    catalog: SystemCatalog,
    acquisitions: Iterable[AcquisitionOpportunity],
    downlink_set: DownlinkOpportunitySet,
    memory_reserve_ratio: float,
    require_full_downlink: bool,
    allow_simultaneous_imaging_downlink: bool,
    downlink_capacity_reserve_ratio: float = 0.0,
) -> ResourcePlanResult:
    """Buduje deterministyczny plan transmisji i profil pamięci.

    Okna są rozpatrywane chronologicznie. Kontakt jest wybierany tylko wtedy,
    gdy na początku okna satelita posiada dane, okno nie koliduje z wcześniej
    wybranym kontaktem oraz — opcjonalnie — nie nakłada się na obrazowanie.
    """

    downlink_set.validate_against(catalog)
    acquisition_list = sorted(
        acquisitions,
        key=lambda item: (item.end_utc, item.satellite_id, item.opportunity_id),
    )
    active_satellites = {
        satellite.satellite_id
        for satellite in catalog.satellites
        if satellite.is_available_for_planning
    }
    active_stations = {
        station.ground_station_id: station
        for station in catalog.ground_stations
        if station.is_active
    }
    candidates = sorted(
        (
            item
            for item in downlink_set.feasible_opportunities
            if item.satellite_id in active_satellites
            and item.ground_station_id in active_stations
        ),
        key=lambda item: (
            item.start_utc,
            item.end_utc,
            -item.capacity_mb,
            item.ground_station_id,
            item.satellite_id,
            item.downlink_opportunity_id,
        ),
    )

    current_by_satellite = {
        satellite.satellite_id: satellite.initial_memory_usage_mb
        for satellite in catalog.satellites
    }
    acquisition_index = 0
    selected_windows: list[DownlinkOpportunity] = []
    planned_windows: list[_PlannedWindow] = []

    for window in candidates:
        while (
            acquisition_index < len(acquisition_list)
            and acquisition_list[acquisition_index].end_utc <= window.start_utc
        ):
            acquisition = acquisition_list[acquisition_index]
            current_by_satellite[acquisition.satellite_id] += (
                acquisition.estimated_data_volume_mb
            )
            acquisition_index += 1

        available = current_by_satellite.get(window.satellite_id, 0.0)
        if available <= 1e-9:
            continue
        if (
            not allow_simultaneous_imaging_downlink
            and _window_conflicts_with_acquisition(window, acquisition_list)
        ):
            continue
        if any(
            selected.satellite_id == window.satellite_id
            and _overlaps(
                selected.start_utc,
                selected.end_utc,
                window.start_utc,
                window.end_utc,
            )
            for selected in selected_windows
        ):
            continue
        station = active_stations[window.ground_station_id]
        if not _station_capacity_available(
            candidate=window,
            selected_windows=selected_windows,
            station_capacity=station.max_simultaneous_contacts,
        ):
            continue

        usable_capacity = window.capacity_mb * (
            1.0 - downlink_capacity_reserve_ratio
        )
        amount = min(usable_capacity, available)
        if amount <= 1e-9:
            continue
        current_by_satellite[window.satellite_id] -= amount
        selected_windows.append(window)
        planned_windows.append(
            _PlannedWindow(
                opportunity=window,
                planned_data_volume_mb=amount,
            )
        )

    return _build_result(
        catalog=catalog,
        acquisitions=acquisition_list,
        planned_windows=planned_windows,
        memory_reserve_ratio=memory_reserve_ratio,
        require_full_downlink=require_full_downlink,
        downlink_capacity_reserve_ratio=downlink_capacity_reserve_ratio,
        horizon_start_utc=downlink_set.horizon_start_utc,
    )


def evaluate_planned_downlinks(
    *,
    catalog: SystemCatalog,
    acquisitions: Iterable[AcquisitionOpportunity],
    downlink_set: DownlinkOpportunitySet,
    planned_amounts_mb: dict[str, float],
    memory_reserve_ratio: float,
    require_full_downlink: bool,
    downlink_capacity_reserve_ratio: float = 0.0,
) -> ResourcePlanResult:
    """Odtwarza profil zasobów dla objętości wyznaczonych przez solver."""

    by_id = {
        item.downlink_opportunity_id: item
        for item in downlink_set.feasible_opportunities
    }
    planned_windows = [
        _PlannedWindow(
            opportunity=by_id[identifier],
            planned_data_volume_mb=amount,
        )
        for identifier, amount in planned_amounts_mb.items()
        if identifier in by_id and amount > 1e-9
    ]
    return _build_result(
        catalog=catalog,
        acquisitions=list(acquisitions),
        planned_windows=planned_windows,
        memory_reserve_ratio=memory_reserve_ratio,
        require_full_downlink=require_full_downlink,
        downlink_capacity_reserve_ratio=downlink_capacity_reserve_ratio,
        horizon_start_utc=downlink_set.horizon_start_utc,
    )


__all__ = [
    "ResourcePlanResult",
    "allocate_downlinks_greedily",
    "evaluate_planned_downlinks",
]
