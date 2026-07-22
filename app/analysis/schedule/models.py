from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

class RequestFulfillmentStatus(str, Enum):
    """Stan realizacji pojedynczego zlecenia."""

    FULLY_SATISFIED = "FULLY_SATISFIED"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    UNASSIGNED = "UNASSIGNED"

class UnassignedReasonCode(str, Enum):
    """Kod przyczyny braku pełnej realizacji zlecenia."""

    NO_FEASIBLE_OPPORTUNITY = "NO_FEASIBLE_OPPORTUNITY"
    MISSING_SAR_OPPORTUNITY = "MISSING_SAR_OPPORTUNITY"
    MISSING_OPTICAL_OPPORTUNITY = "MISSING_OPTICAL_OPPORTUNITY"
    SATELLITE_INACTIVE = "SATELLITE_INACTIVE"
    TRANSITION_CONFLICT = "TRANSITION_CONFLICT"
    MEMORY_LIMIT = "MEMORY_LIMIT"
    ACQUISITION_LIMIT = "ACQUISITION_LIMIT"
    IMAGING_TIME_LIMIT = "IMAGING_TIME_LIMIT"
    DUAL_SEPARATION_LIMIT = "DUAL_SEPARATION_LIMIT"
    GREEDY_ORDERING = "GREEDY_ORDERING"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True)
class SatelliteKPI:
    """Wskaźniki wykorzystania pojedynczego satelity."""

    satellite_id: str
    sensor_type: str
    scheduled_acquisitions: int
    imaging_time_s: float
    imaging_time_limit_s: float
    imaging_utilization_ratio: float
    generated_data_mb: float
    downlinked_data_mb: float
    selected_downlink_windows: int
    peak_memory_usage_mb: float
    delivery_complete: bool
    initial_memory_usage_mb: float
    planning_memory_limit_mb: float
    final_memory_usage_mb: float
    memory_utilization_ratio: float
    acquisition_limit: int
    acquisition_utilization_ratio: float

@dataclass(frozen=True)
class RequestDiagnostic:
    """Wynik realizacji oraz diagnostyka pojedynczego zlecenia."""

    request_id: str
    request_mode: str
    priority: int
    is_mandatory: bool
    fulfillment_status: str
    scheduled_entry_count: int
    scheduled_sensor_types: tuple[str, ...]
    feasible_opportunity_count: int
    feasible_sar_count: int
    feasible_optical_count: int
    reason_codes: tuple[str, ...]

@dataclass(frozen=True)
class EntryKPI:
    """Wiersz raportu szczegółowego zaplanowanej akwizycji."""

    entry_id: str
    opportunity_id: str
    request_id: str
    satellite_id: str
    sensor_type: str
    mode_id: str
    start_utc: str
    end_utc: str
    duration_s: float
    estimated_data_volume_mb: float
    objective_contribution: float
    quality_score: float
    coverage_ratio: float
    cloud_cover: float | None
    incidence_angle_deg: float | None
    off_nadir_angle_deg: float

@dataclass(frozen=True)
class ScheduleAnalysis:
    """Kompletny raport KPI dla harmonogramu."""

    schedule_id: str
    schedule_status: str

    total_active_requests: int
    requests_with_entries: int
    fully_satisfied_requests: int
    partially_satisfied_requests: int
    unassigned_requests: int

    mandatory_requests: int
    mandatory_satisfied_requests: int

    satisfaction_ratio: float
    mandatory_satisfaction_ratio: float

    total_acquisitions: int
    sar_acquisitions: int
    optical_acquisitions: int

    total_duration_s: float
    total_data_volume_mb: float
    total_downlinked_data_mb: float
    selected_downlink_windows: int
    delivery_completion_ratio: float
    objective_value: float

    average_selected_quality: float
    average_selected_coverage: float
    selected_to_feasible_ratio: float

    request_diagnostics: tuple[RequestDiagnostic, ...]
    satellite_kpis: tuple[SatelliteKPI, ...]
    entry_kpis: tuple[EntryKPI, ...]

    unassigned_reason_counts: dict[str, int]

    def kpi_rows(self) -> list[dict[str, object]]:
        """Zwraca główne KPI w formacie przeznaczonym do CSV."""

        rows: list[dict[str, object]] = [
            {
                "metric": "schedule_id",
                "value": self.schedule_id,
            },
            {
                "metric": "schedule_status",
                "value": self.schedule_status,
            },
            {
                "metric": "total_active_requests",
                "value": self.total_active_requests,
            },
            {
                "metric": "requests_with_entries",
                "value": self.requests_with_entries,
            },
            {
                "metric": "fully_satisfied_requests",
                "value": self.fully_satisfied_requests,
            },
            {
                "metric": "partially_satisfied_requests",
                "value": self.partially_satisfied_requests,
            },
            {
                "metric": "unassigned_requests",
                "value": self.unassigned_requests,
            },
            {
                "metric": "mandatory_requests",
                "value": self.mandatory_requests,
            },
            {
                "metric": "mandatory_satisfied_requests",
                "value": self.mandatory_satisfied_requests,
            },
            {
                "metric": "satisfaction_ratio",
                "value": self.satisfaction_ratio,
            },
            {
                "metric": "mandatory_satisfaction_ratio",
                "value": self.mandatory_satisfaction_ratio,
            },
            {
                "metric": "total_acquisitions",
                "value": self.total_acquisitions,
            },
            {
                "metric": "sar_acquisitions",
                "value": self.sar_acquisitions,
            },
            {
                "metric": "optical_acquisitions",
                "value": self.optical_acquisitions,
            },
            {
                "metric": "total_duration_s",
                "value": self.total_duration_s,
            },
            {
                "metric": "total_data_volume_mb",
                "value": self.total_data_volume_mb,
            },
            {
                "metric": "total_downlinked_data_mb",
                "value": self.total_downlinked_data_mb,
            },
            {
                "metric": "selected_downlink_windows",
                "value": self.selected_downlink_windows,
            },
            {
                "metric": "delivery_completion_ratio",
                "value": self.delivery_completion_ratio,
            },
            {
                "metric": "objective_value",
                "value": self.objective_value,
            },
            {
                "metric": "average_selected_quality",
                "value": self.average_selected_quality,
            },
            {
                "metric": "average_selected_coverage",
                "value": self.average_selected_coverage,
            },
            {
                "metric": "selected_to_feasible_ratio",
                "value": self.selected_to_feasible_ratio,
            },
        ]

        for reason, count in sorted(
            self.unassigned_reason_counts.items()
        ):
            rows.append(
                {
                    "metric": f"unassigned_reason_{reason}",
                    "value": count,
                }
            )

        return rows
