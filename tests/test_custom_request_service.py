from datetime import datetime, timedelta, timezone

from app.models.enums import RequestMode, SensorType
from app.models.geometry import PointGeometry
from app.custom_requests import (
    build_custom_request,
    serialize_custom_requests,
)


def test_build_custom_optical_request_from_map_geometry() -> None:
    start = datetime(2026, 7, 16, 10, tzinfo=timezone.utc)
    request = build_custom_request(
        request_id="REQ-CUSTOM-001",
        name="Warszawa",
        geometry=PointGeometry(coordinates=(21.0122, 52.2297)),
        priority=8,
        earliest_start_utc=start,
        latest_end_utc=start + timedelta(hours=4),
        request_mode=RequestMode.SINGLE,
        requested_sensor_types=[SensorType.OPTICAL],
        max_resolution_m=0.5,
        minimum_coverage_ratio=0.9,
        max_cloud_cover=0.2,
        max_incidence_angle_deg=None,
        max_off_nadir_deg=45,
        is_mandatory=True,
    )

    assert request.requires_optical
    assert request.geometry.type == "Point"
    assert '"REQ-CUSTOM-001"' in serialize_custom_requests([request])


def test_dual_request_supports_separate_sar_and_eo_resolution_limits() -> None:
    start = datetime(2026, 7, 16, 10, tzinfo=timezone.utc)
    request = build_custom_request(
        request_id="REQ-CUSTOM-DUAL-001",
        name="Warszawa dual",
        geometry=PointGeometry(coordinates=(21.0122, 52.2297)),
        priority=9,
        earliest_start_utc=start,
        latest_end_utc=start + timedelta(hours=8),
        request_mode=RequestMode.DUAL_REQUIRED,
        requested_sensor_types=[SensorType.SAR, SensorType.OPTICAL],
        max_resolution_m=1.0,
        max_sar_resolution_m=1.0,
        max_optical_resolution_m=0.3,
        minimum_coverage_ratio=0.9,
        max_cloud_cover=0.2,
        max_incidence_angle_deg=45.0,
        max_off_nadir_deg=45.0,
        is_mandatory=False,
    )

    assert request.minimum_required_acquisitions == 2
    assert request.resolution_limit_for(SensorType.SAR) == 1.0
    assert request.resolution_limit_for(SensorType.OPTICAL) == 0.3
