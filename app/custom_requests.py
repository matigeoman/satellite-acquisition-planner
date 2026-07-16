from __future__ import annotations

import json
from datetime import datetime

from app.models.enums import RequestMode, SensorType
from app.models.geometry import TargetGeometry
from app.models.request import ObservationRequest


def build_custom_request(
    *,
    request_id: str,
    name: str,
    geometry: TargetGeometry,
    priority: int,
    earliest_start_utc: datetime,
    latest_end_utc: datetime,
    request_mode: RequestMode,
    requested_sensor_types: list[SensorType],
    max_resolution_m: float,
    minimum_coverage_ratio: float,
    max_cloud_cover: float | None,
    max_incidence_angle_deg: float | None,
    max_off_nadir_deg: float | None,
    is_mandatory: bool,
    notes: str | None = None,
) -> ObservationRequest:
    """Tworzy walidowane zlecenie z geometrii pochodzącej z mapy."""

    return ObservationRequest(
        request_id=request_id,
        name=name,
        geometry=geometry,
        priority=priority,
        earliest_start_utc=earliest_start_utc,
        latest_end_utc=latest_end_utc,
        request_mode=request_mode,
        requested_sensor_types=requested_sensor_types,
        max_resolution_m=max_resolution_m,
        minimum_coverage_ratio=minimum_coverage_ratio,
        max_cloud_cover=max_cloud_cover,
        max_incidence_angle_deg=max_incidence_angle_deg,
        max_off_nadir_deg=max_off_nadir_deg,
        is_mandatory=is_mandatory,
        notes=notes,
    )


def serialize_custom_requests(requests: list[ObservationRequest]) -> str:
    """Eksportuje listę zleceń do czytelnego JSON UTF-8."""

    return json.dumps(
        [request.model_dump(mode="json") for request in requests],
        ensure_ascii=False,
        indent=2,
    )
