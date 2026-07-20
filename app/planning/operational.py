from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models.enums import ObservationSide, SensorType
from app.models.imaging import ImagingMode
from app.models.opportunity import AcquisitionOpportunity
from app.models.request import ObservationRequest
from app.models.satellite import Satellite
from app.models.sensor import Sensor


class OperationalPlannerConfig(Protocol):
    """Wspólne parametry modelu operacyjnego obu planerów."""

    use_dynamic_transition_model: bool
    eo_stabilization_time_s: float
    sar_stabilization_time_s: float
    sar_side_switch_penalty_s: float
    sar_mode_switch_penalty_s: float
    sar_slew_rate_deg_s: float
    sar_pass_gap_s: float
    sar_max_acquisitions_per_pass: int


@dataclass(frozen=True)
class TransitionBreakdown:
    """Składniki czasu przejścia pomiędzy dwiema akwizycjami."""

    model: str
    angular_distance_deg: float
    slew_time_s: float
    stabilization_time_s: float
    side_switch_penalty_s: float
    mode_switch_penalty_s: float
    sensor_service_time_s: float
    total_time_s: float


def signed_look_angle_deg(opportunity: AcquisitionOpportunity) -> float:
    """Zwraca podpisany kąt obserwacji: LEFT < 0, RIGHT > 0, NADIR = 0."""

    if opportunity.observation_side == ObservationSide.LEFT:
        return -opportunity.off_nadir_angle_deg
    if opportunity.observation_side == ObservationSide.RIGHT:
        return opportunity.off_nadir_angle_deg
    return 0.0


def pleiades_neo_slew_time_s(angular_distance_deg: float) -> float:
    """Interpoluje publiczne czasy zwrotu Pléiades Neo.

    Punkty modelu: 0°/0 s, 10°/7 s, 30°/12 s oraz 60°/20 s.
    Powyżej 60° używana jest liniowa ekstrapolacja nachyleniem ostatniego
    przedziału. Funkcja opisuje model jawny, a nie gwarancję operatora.
    """

    angle = max(0.0, float(angular_distance_deg))
    anchors = (
        (0.0, 0.0),
        (10.0, 7.0),
        (30.0, 12.0),
        (60.0, 20.0),
    )

    for (left_angle, left_time), (right_angle, right_time) in zip(
        anchors,
        anchors[1:],
    ):
        if angle <= right_angle:
            ratio = (angle - left_angle) / (right_angle - left_angle)
            return left_time + ratio * (right_time - left_time)

    last_angle, last_time = anchors[-1]
    previous_angle, previous_time = anchors[-2]
    slope = (last_time - previous_time) / (last_angle - previous_angle)
    return last_time + (angle - last_angle) * slope


def transition_breakdown(
    *,
    first: AcquisitionOpportunity,
    second: AcquisitionOpportunity,
    satellite: Satellite,
    sensor: Sensor,
    modes_by_id: dict[str, ImagingMode],
    config: OperationalPlannerConfig,
) -> TransitionBreakdown:
    """Oblicza kierunkowy czas przejścia first -> second."""

    sensor_service_time_s = sensor.cooldown_time_s + sensor.warmup_time_s

    if not config.use_dynamic_transition_model:
        total = max(
            satellite.minimum_transition_time_s,
            sensor_service_time_s,
        )
        return TransitionBreakdown(
            model="STATIC",
            angular_distance_deg=0.0,
            slew_time_s=0.0,
            stabilization_time_s=0.0,
            side_switch_penalty_s=0.0,
            mode_switch_penalty_s=0.0,
            sensor_service_time_s=sensor_service_time_s,
            total_time_s=total,
        )

    angular_distance_deg = abs(
        signed_look_angle_deg(second) - signed_look_angle_deg(first)
    )

    if first.sensor_type == SensorType.OPTICAL:
        slew_time_s = pleiades_neo_slew_time_s(angular_distance_deg)
        stabilization_time_s = config.eo_stabilization_time_s
        total = max(
            sensor_service_time_s,
            slew_time_s + stabilization_time_s,
        )
        return TransitionBreakdown(
            model="PLEIADES_NEO_DYNAMIC",
            angular_distance_deg=angular_distance_deg,
            slew_time_s=slew_time_s,
            stabilization_time_s=stabilization_time_s,
            side_switch_penalty_s=0.0,
            mode_switch_penalty_s=0.0,
            sensor_service_time_s=sensor_service_time_s,
            total_time_s=total,
        )

    slew_time_s = angular_distance_deg / config.sar_slew_rate_deg_s
    stabilization_time_s = config.sar_stabilization_time_s
    side_switch_penalty_s = 0.0
    if first.observation_side != second.observation_side:
        side_switch_penalty_s = config.sar_side_switch_penalty_s

    first_mode = modes_by_id[first.mode_id]
    second_mode = modes_by_id[second.mode_id]
    mode_switch_penalty_s = 0.0
    if first_mode.mode_category != second_mode.mode_category:
        mode_switch_penalty_s = config.sar_mode_switch_penalty_s

    total = max(
        sensor_service_time_s,
        slew_time_s
        + stabilization_time_s
        + side_switch_penalty_s
        + mode_switch_penalty_s,
    )
    return TransitionBreakdown(
        model="ICEYE_DYNAMIC",
        angular_distance_deg=angular_distance_deg,
        slew_time_s=slew_time_s,
        stabilization_time_s=stabilization_time_s,
        side_switch_penalty_s=side_switch_penalty_s,
        mode_switch_penalty_s=mode_switch_penalty_s,
        sensor_service_time_s=sensor_service_time_s,
        total_time_s=total,
    )


def required_transition_time_s(
    *,
    first: AcquisitionOpportunity,
    second: AcquisitionOpportunity,
    satellite: Satellite,
    sensor: Sensor,
    modes_by_id: dict[str, ImagingMode],
    config: OperationalPlannerConfig,
) -> float:
    """Zwraca wymagany kierunkowy czas przejścia first -> second."""

    return transition_breakdown(
        first=first,
        second=second,
        satellite=satellite,
        sensor=sensor,
        modes_by_id=modes_by_id,
        config=config,
    ).total_time_s


def dual_separation_s(
    first: AcquisitionOpportunity,
    second: AcquisitionOpportunity,
) -> float:
    """Zwraca odstęp pomiędzy środkami dwóch akwizycji."""

    first_midpoint = first.start_utc + (first.end_utc - first.start_utc) / 2
    second_midpoint = second.start_utc + (second.end_utc - second.start_utc) / 2
    return abs((second_midpoint - first_midpoint).total_seconds())


def dual_pair_is_compatible(
    request: ObservationRequest,
    first: AcquisitionOpportunity,
    second: AcquisitionOpportunity,
) -> bool:
    """Sprawdza typy sensorów i maksymalny odstęp pary SAR + EO."""

    if first.request_id != request.request_id or second.request_id != request.request_id:
        return False
    if {first.sensor_type, second.sensor_type} != {
        SensorType.SAR,
        SensorType.OPTICAL,
    }:
        return False
    if request.max_dual_separation_s is None:
        return True
    return dual_separation_s(first, second) <= request.max_dual_separation_s + 1e-9


def request_is_fulfilled(
    request: ObservationRequest,
    opportunities: list[AcquisitionOpportunity],
) -> bool:
    """Sprawdza pełną realizację zlecenia, w tym limit czasu SAR–EO."""

    if not opportunities:
        return False
    if request.request_mode.value != "DUAL_REQUIRED":
        return True

    sar_opportunities = [
        opportunity
        for opportunity in opportunities
        if opportunity.sensor_type == SensorType.SAR
    ]
    optical_opportunities = [
        opportunity
        for opportunity in opportunities
        if opportunity.sensor_type == SensorType.OPTICAL
    ]
    return any(
        dual_pair_is_compatible(request, sar, optical)
        for sar in sar_opportunities
        for optical in optical_opportunities
    )


def build_pass_index(
    opportunities: list[AcquisitionOpportunity],
    *,
    pass_gap_s: float,
) -> dict[str, int]:
    """Grupuje okazje SAR w deterministyczne przeloty według przerwy czasowej."""

    ordered = sorted(
        opportunities,
        key=lambda opportunity: (
            opportunity.start_utc,
            opportunity.end_utc,
            opportunity.opportunity_id,
        ),
    )
    if not ordered:
        return {}

    result: dict[str, int] = {}
    pass_number = 0
    previous_end = ordered[0].end_utc
    result[ordered[0].opportunity_id] = pass_number

    for opportunity in ordered[1:]:
        gap_s = (opportunity.start_utc - previous_end).total_seconds()
        if gap_s > pass_gap_s:
            pass_number += 1
        result[opportunity.opportunity_id] = pass_number
        previous_end = max(previous_end, opportunity.end_utc)

    return result
