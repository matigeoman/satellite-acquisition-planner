from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.enums import (
    ObservationSide,
    RequestMode,
    SensorType,
)
from app.models.geometry import PointGeometry
from app.models.opportunity import AcquisitionOpportunity
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.planning.config import CpSatPlannerConfig, GreedyPlannerConfig
from app.planning.cp_sat import build_cp_sat_schedule
from app.planning.greedy import build_greedy_schedule
from app.planning.operational import (
    dual_pair_is_compatible,
    pleiades_neo_slew_time_s,
    transition_breakdown,
)
from app.services.public_scenario_service import build_public_system_catalog


HORIZON_START = datetime(2026, 7, 17, 0, 0, tzinfo=timezone.utc)
HORIZON_END = HORIZON_START + timedelta(hours=12)


def _request(
    *,
    request_id: str,
    mode: RequestMode,
    sensors: list[SensorType],
    max_dual_separation_s: float | None = None,
    priority: int = 5,
) -> ObservationRequest:
    return ObservationRequest(
        request_id=request_id,
        name=request_id,
        geometry=PointGeometry(coordinates=(21.0, 52.0)),
        priority=priority,
        earliest_start_utc=HORIZON_START,
        latest_end_utc=HORIZON_END,
        request_mode=mode,
        requested_sensor_types=sensors,
        max_resolution_m=30.0,
        max_sar_resolution_m=(30.0 if SensorType.SAR in sensors else None),
        max_optical_resolution_m=(2.0 if SensorType.OPTICAL in sensors else None),
        minimum_coverage_ratio=0.8,
        max_cloud_cover=(0.5 if SensorType.OPTICAL in sensors else None),
        max_incidence_angle_deg=(40.0 if SensorType.SAR in sensors else None),
        max_off_nadir_deg=52.0,
        max_dual_separation_s=max_dual_separation_s,
    )


def _opportunity(
    *,
    opportunity_id: str,
    request_id: str,
    sensor_type: SensorType,
    start: datetime,
    side: ObservationSide,
    off_nadir_deg: float,
    quality: float = 0.8,
    satellite_id: str | None = None,
    mode_id: str | None = None,
) -> AcquisitionOpportunity:
    catalog = build_public_system_catalog()
    if sensor_type == SensorType.SAR:
        satellite_id = satellite_id or "SAR-01"
        sensor = catalog.get_sensor("SENSOR-SAR-ICEYE-PUBLIC")
        selected_mode_id = mode_id or "MODE-SAR-ICEYE-SPOT"
        mode = next(
            candidate
            for candidate in sensor.imaging_modes
            if candidate.mode_id == selected_mode_id
        )
        duration_s = mode.min_acquisition_duration_s
        return AcquisitionOpportunity(
            opportunity_id=opportunity_id,
            request_id=request_id,
            satellite_id=satellite_id,
            sensor_id=sensor.sensor_id,
            mode_id=mode.mode_id,
            sensor_type=sensor_type,
            start_utc=start,
            end_utc=start + timedelta(seconds=duration_s),
            observation_side=side,
            off_nadir_angle_deg=off_nadir_deg,
            incidence_angle_deg=25.0,
            coverage_ratio=1.0,
            quality_score=quality,
            estimated_data_volume_mb=duration_s * mode.data_rate_mb_s,
        )

    satellite_id = satellite_id or "EO-01"
    sensor = catalog.get_sensor("SENSOR-EO-PLEIADES-NEO-PUBLIC")
    selected_mode_id = mode_id or "MODE-OPT-PLEIADES-NEO-PAN"
    mode = next(
        candidate
        for candidate in sensor.imaging_modes
        if candidate.mode_id == selected_mode_id
    )
    duration_s = mode.min_acquisition_duration_s
    return AcquisitionOpportunity(
        opportunity_id=opportunity_id,
        request_id=request_id,
        satellite_id=satellite_id,
        sensor_id=sensor.sensor_id,
        mode_id=mode.mode_id,
        sensor_type=sensor_type,
        start_utc=start,
        end_utc=start + timedelta(seconds=duration_s),
        observation_side=side,
        off_nadir_angle_deg=off_nadir_deg,
        cloud_cover=0.1,
        sun_elevation_deg=30.0,
        coverage_ratio=1.0,
        quality_score=quality,
        estimated_data_volume_mb=duration_s * mode.data_rate_mb_s,
    )


def _sets(
    requests: list[ObservationRequest],
    opportunities: list[AcquisitionOpportunity],
) -> tuple[ObservationRequestSet, AcquisitionOpportunitySet]:
    request_set = ObservationRequestSet(
        request_set_id="REQSET-OPERATIONAL-TEST",
        name="Operational test requests",
        version="1.0.0",
        horizon_start_utc=HORIZON_START,
        horizon_end_utc=HORIZON_END,
        generated_at_utc=HORIZON_START,
        requests=requests,
    )
    opportunity_set = AcquisitionOpportunitySet(
        opportunity_set_id="OPPSET-OPERATIONAL-TEST",
        name="Operational test opportunities",
        version="1.0.0",
        catalog_id="CATALOG-PUBLIC-PLANNER",
        request_set_id=request_set.request_set_id,
        horizon_start_utc=HORIZON_START,
        horizon_end_utc=HORIZON_END,
        generated_at_utc=HORIZON_START,
        random_seed=0,
        opportunities=opportunities,
    )
    return request_set, opportunity_set


def test_pleiades_neo_slew_interpolation() -> None:
    assert pleiades_neo_slew_time_s(0.0) == pytest.approx(0.0)
    assert pleiades_neo_slew_time_s(10.0) == pytest.approx(7.0)
    assert pleiades_neo_slew_time_s(20.0) == pytest.approx(9.5)
    assert pleiades_neo_slew_time_s(30.0) == pytest.approx(12.0)
    assert pleiades_neo_slew_time_s(60.0) == pytest.approx(20.0)
    assert pleiades_neo_slew_time_s(90.0) == pytest.approx(28.0)


def test_iceye_transition_adds_side_and_mode_penalties() -> None:
    catalog = build_public_system_catalog()
    satellite = catalog.get_satellite("SAR-01")
    sensor = catalog.get_sensor(satellite.sensor_id)
    modes = {
        mode.mode_id: mode
        for catalog_sensor in catalog.sensors
        for mode in catalog_sensor.imaging_modes
    }
    first = _opportunity(
        opportunity_id="OPP-SAR-FIRST",
        request_id="REQ-DUAL-001",
        sensor_type=SensorType.SAR,
        start=HORIZON_START,
        side=ObservationSide.LEFT,
        off_nadir_deg=20.0,
        mode_id="MODE-SAR-ICEYE-SPOT",
    )
    second = _opportunity(
        opportunity_id="OPP-SAR-SECOND",
        request_id="REQ-DUAL-001",
        sensor_type=SensorType.SAR,
        start=HORIZON_START + timedelta(minutes=1),
        side=ObservationSide.RIGHT,
        off_nadir_deg=20.0,
        mode_id="MODE-SAR-ICEYE-STRIP",
    )
    breakdown = transition_breakdown(
        first=first,
        second=second,
        satellite=satellite,
        sensor=sensor,
        modes_by_id=modes,
        config=GreedyPlannerConfig(use_dynamic_transition_model=True),
    )
    assert breakdown.model == "ICEYE_DYNAMIC"
    assert breakdown.angular_distance_deg == pytest.approx(40.0)
    assert breakdown.slew_time_s == pytest.approx(20.0)
    assert breakdown.stabilization_time_s == pytest.approx(10.0)
    assert breakdown.side_switch_penalty_s == pytest.approx(60.0)
    assert breakdown.mode_switch_penalty_s == pytest.approx(15.0)
    assert breakdown.total_time_s == pytest.approx(105.0)


def test_dual_pair_limit_uses_acquisition_midpoints() -> None:
    request = _request(
        request_id="REQ-DUAL-001",
        mode=RequestMode.DUAL_REQUIRED,
        sensors=[SensorType.SAR, SensorType.OPTICAL],
        max_dual_separation_s=3600.0,
    )
    sar = _opportunity(
        opportunity_id="OPP-DUAL-SAR",
        request_id=request.request_id,
        sensor_type=SensorType.SAR,
        start=HORIZON_START,
        side=ObservationSide.LEFT,
        off_nadir_deg=25.0,
    )
    near_eo = _opportunity(
        opportunity_id="OPP-DUAL-EO-NEAR",
        request_id=request.request_id,
        sensor_type=SensorType.OPTICAL,
        start=HORIZON_START + timedelta(minutes=59),
        side=ObservationSide.RIGHT,
        off_nadir_deg=15.0,
    )
    far_eo = near_eo.model_copy(
        update={
            "opportunity_id": "OPP-DUAL-EO-FAR",
            "start_utc": HORIZON_START + timedelta(hours=2),
            "end_utc": HORIZON_START + timedelta(hours=2, seconds=5),
        }
    )
    assert dual_pair_is_compatible(request, sar, near_eo)
    assert not dual_pair_is_compatible(request, sar, far_eo)


@pytest.mark.parametrize("algorithm", ["GREEDY", "CP_SAT"])
def test_dual_required_planners_select_only_temporally_compatible_pair(
    algorithm: str,
) -> None:
    catalog = build_public_system_catalog()
    request = _request(
        request_id="REQ-DUAL-001",
        mode=RequestMode.DUAL_REQUIRED,
        sensors=[SensorType.SAR, SensorType.OPTICAL],
        max_dual_separation_s=3600.0,
    )
    sar = _opportunity(
        opportunity_id="OPP-DUAL-SAR",
        request_id=request.request_id,
        sensor_type=SensorType.SAR,
        start=HORIZON_START + timedelta(minutes=10),
        side=ObservationSide.LEFT,
        off_nadir_deg=25.0,
        quality=0.8,
    )
    eo_near = _opportunity(
        opportunity_id="OPP-DUAL-EO-NEAR",
        request_id=request.request_id,
        sensor_type=SensorType.OPTICAL,
        start=HORIZON_START + timedelta(minutes=40),
        side=ObservationSide.RIGHT,
        off_nadir_deg=15.0,
        quality=0.6,
    )
    eo_far = _opportunity(
        opportunity_id="OPP-DUAL-EO-FAR",
        request_id=request.request_id,
        sensor_type=SensorType.OPTICAL,
        start=HORIZON_START + timedelta(hours=4),
        side=ObservationSide.RIGHT,
        off_nadir_deg=15.0,
        quality=1.0,
    )
    request_set, opportunity_set = _sets(
        [request],
        [sar, eo_near, eo_far],
    )

    if algorithm == "GREEDY":
        schedule = build_greedy_schedule(
            catalog,
            request_set,
            opportunity_set,
        )
    else:
        schedule = build_cp_sat_schedule(
            catalog,
            request_set,
            opportunity_set,
            config=CpSatPlannerConfig(max_time_s=5.0),
        )

    assert {entry.opportunity_id for entry in schedule.active_entries} == {
        sar.opportunity_id,
        eo_near.opportunity_id,
    }


@pytest.mark.parametrize("algorithm", ["GREEDY", "CP_SAT"])
def test_dynamic_pleiades_transition_replaces_legacy_static_gap(
    algorithm: str,
) -> None:
    catalog = build_public_system_catalog()
    requests = [
        _request(
            request_id="REQ-EO-001",
            mode=RequestMode.SINGLE,
            sensors=[SensorType.OPTICAL],
        ),
        _request(
            request_id="REQ-EO-002",
            mode=RequestMode.SINGLE,
            sensors=[SensorType.OPTICAL],
        ),
    ]
    first = _opportunity(
        opportunity_id="OPP-EO-FIRST",
        request_id=requests[0].request_id,
        sensor_type=SensorType.OPTICAL,
        start=HORIZON_START + timedelta(minutes=10),
        side=ObservationSide.LEFT,
        off_nadir_deg=30.0,
    )
    second = _opportunity(
        opportunity_id="OPP-EO-SECOND",
        request_id=requests[1].request_id,
        sensor_type=SensorType.OPTICAL,
        start=first.end_utc + timedelta(seconds=30),
        side=ObservationSide.RIGHT,
        off_nadir_deg=30.0,
    )
    request_set, opportunity_set = _sets(requests, [first, second])

    if algorithm == "GREEDY":
        static_schedule = build_greedy_schedule(
            catalog,
            request_set,
            opportunity_set,
            config=GreedyPlannerConfig(use_dynamic_transition_model=False),
        )
        dynamic_schedule = build_greedy_schedule(
            catalog,
            request_set,
            opportunity_set,
            config=GreedyPlannerConfig(use_dynamic_transition_model=True),
        )
    else:
        static_schedule = build_cp_sat_schedule(
            catalog,
            request_set,
            opportunity_set,
            config=CpSatPlannerConfig(
                use_dynamic_transition_model=False,
                max_time_s=5.0,
            ),
        )
        dynamic_schedule = build_cp_sat_schedule(
            catalog,
            request_set,
            opportunity_set,
            config=CpSatPlannerConfig(
                use_dynamic_transition_model=True,
                max_time_s=5.0,
            ),
        )

    assert static_schedule.total_acquisitions == 1
    assert dynamic_schedule.total_acquisitions == 2


@pytest.mark.parametrize("algorithm", ["GREEDY", "CP_SAT"])
def test_iceye_per_pass_limit_is_enforced(algorithm: str) -> None:
    catalog = build_public_system_catalog()
    requests: list[ObservationRequest] = []
    opportunities: list[AcquisitionOpportunity] = []
    for index in range(4):
        request = _request(
            request_id=f"REQ-SAR-{index + 1:03d}",
            mode=RequestMode.SINGLE,
            sensors=[SensorType.SAR],
            priority=10 - index,
        )
        requests.append(request)
        opportunities.append(
            _opportunity(
                opportunity_id=f"OPP-SAR-{index + 1:03d}",
                request_id=request.request_id,
                sensor_type=SensorType.SAR,
                start=HORIZON_START
                + timedelta(minutes=10, seconds=index * 30),
                side=ObservationSide.LEFT,
                off_nadir_deg=20.0,
            )
        )
    request_set, opportunity_set = _sets(requests, opportunities)

    if algorithm == "GREEDY":
        schedule = build_greedy_schedule(
            catalog,
            request_set,
            opportunity_set,
            config=GreedyPlannerConfig(
                use_dynamic_transition_model=True,
                sar_max_acquisitions_per_pass=3,
            ),
        )
    else:
        schedule = build_cp_sat_schedule(
            catalog,
            request_set,
            opportunity_set,
            config=CpSatPlannerConfig(
                use_dynamic_transition_model=True,
                sar_max_acquisitions_per_pass=3,
                max_time_s=5.0,
            ),
        )

    assert schedule.total_acquisitions == 3


def test_single_request_rejects_dual_separation_limit() -> None:
    with pytest.raises(ValueError, match="SINGLE"):
        _request(
            request_id="REQ-EO-001",
            mode=RequestMode.SINGLE,
            sensors=[SensorType.OPTICAL],
            max_dual_separation_s=3600.0,
        )
