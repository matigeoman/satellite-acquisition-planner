from datetime import datetime, timezone

from app.models.enums import (
    ObservationSide,
    RequestMode,
    SensorType,
)
from app.models.geometry import PointGeometry
from app.models.opportunity import AcquisitionOpportunity
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.planning.config import GreedyPlannerConfig
from app.planning.scoring import (
    acquisition_score,
    calculate_objective_contributions,
    request_reward,
)


START = datetime(2026, 7, 15, tzinfo=timezone.utc)
END = datetime(2026, 7, 16, tzinfo=timezone.utc)


def _request(
    *,
    request_id: str,
    mode: RequestMode,
    mandatory: bool = False,
) -> ObservationRequest:
    sensor_types = (
        [SensorType.SAR]
        if mode == RequestMode.SINGLE
        else [SensorType.SAR, SensorType.OPTICAL]
    )

    return ObservationRequest(
        request_id=request_id,
        name=request_id,
        geometry=PointGeometry(coordinates=(21.0, 52.0)),
        priority=10,
        earliest_start_utc=START,
        latest_end_utc=END,
        request_mode=mode,
        requested_sensor_types=sensor_types,
        max_resolution_m=1.0,
        minimum_coverage_ratio=0.8,
        max_cloud_cover=(
            0.3 if SensorType.OPTICAL in sensor_types else None
        ),
        max_incidence_angle_deg=(
            45.0 if SensorType.SAR in sensor_types else None
        ),
        is_mandatory=mandatory,
    )


def _opportunity(
    *,
    opportunity_id: str,
    request_id: str,
    sensor_type: SensorType,
    quality: float,
    coverage: float,
) -> AcquisitionOpportunity:
    is_sar = sensor_type == SensorType.SAR

    return AcquisitionOpportunity(
        opportunity_id=opportunity_id,
        request_id=request_id,
        satellite_id="SAR-01" if is_sar else "EO-01",
        sensor_id="SENSOR-SAR-01" if is_sar else "SENSOR-EO-01",
        mode_id="MODE-SAR-01" if is_sar else "MODE-OPT-01",
        sensor_type=sensor_type,
        start_utc=START,
        end_utc=START.replace(minute=1),
        observation_side=(
            ObservationSide.RIGHT
            if is_sar
            else ObservationSide.NADIR
        ),
        off_nadir_angle_deg=30.0 if is_sar else 0.0,
        incidence_angle_deg=35.0 if is_sar else None,
        cloud_cover=None if is_sar else 0.1,
        sun_elevation_deg=None if is_sar else 35.0,
        coverage_ratio=coverage,
        quality_score=quality,
        estimated_data_volume_mb=100.0,
        is_feasible=True,
    )


def _request_set(*requests: ObservationRequest) -> ObservationRequestSet:
    return ObservationRequestSet(
        request_set_id="REQSET-SCORING-TEST",
        name="Scoring test",
        version="1.0.0",
        horizon_start_utc=START,
        horizon_end_utc=END,
        requests=list(requests),
    )


def test_request_reward_is_counted_once() -> None:
    config = GreedyPlannerConfig()
    request = _request(
        request_id="REQ-SINGLE-001",
        mode=RequestMode.SINGLE,
        mandatory=True,
    )

    assert request_reward(request, config) == 200.0


def test_acquisition_score_uses_quality_and_coverage() -> None:
    config = GreedyPlannerConfig()
    opportunity = _opportunity(
        opportunity_id="OPP-SCORING-001",
        request_id="REQ-SINGLE-001",
        sensor_type=SensorType.SAR,
        quality=0.8,
        coverage=0.9,
    )

    assert acquisition_score(opportunity, config) == 4.2


def test_dual_required_splits_request_reward_between_two_entries() -> None:
    config = GreedyPlannerConfig()
    request = _request(
        request_id="REQ-DUAL-001",
        mode=RequestMode.DUAL_REQUIRED,
        mandatory=True,
    )
    sar = _opportunity(
        opportunity_id="OPP-DUAL-SAR-001",
        request_id=request.request_id,
        sensor_type=SensorType.SAR,
        quality=0.8,
        coverage=0.9,
    )
    optical = _opportunity(
        opportunity_id="OPP-DUAL-EO-001",
        request_id=request.request_id,
        sensor_type=SensorType.OPTICAL,
        quality=0.7,
        coverage=0.8,
    )

    contributions = calculate_objective_contributions(
        request_set=_request_set(request),
        selected_opportunities=[sar, optical],
        config=config,
    )

    assert round(sum(contributions.values()), 6) == 207.9


def test_incomplete_dual_required_receives_no_request_reward() -> None:
    config = GreedyPlannerConfig()
    request = _request(
        request_id="REQ-DUAL-002",
        mode=RequestMode.DUAL_REQUIRED,
        mandatory=True,
    )
    sar = _opportunity(
        opportunity_id="OPP-DUAL-SAR-002",
        request_id=request.request_id,
        sensor_type=SensorType.SAR,
        quality=0.8,
        coverage=0.9,
    )

    contributions = calculate_objective_contributions(
        request_set=_request_set(request),
        selected_opportunities=[sar],
        config=config,
    )

    assert contributions[sar.opportunity_id] == 4.2
