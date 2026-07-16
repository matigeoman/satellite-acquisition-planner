from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from app.catalogs import ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE
from app.integrations.access.models import AccessCalculationResult
from app.integrations.orbits.models import (
    PropagatedState,
    SatelliteFamily,
    SatelliteGroundTrack,
)
from app.models.geometry import PointGeometry, PolygonGeometry, TargetGeometry
from app.models.request import ObservationRequest
from app.services.contracts.planning import PlanningResult


SAR_COLOR = (255, 99, 106, 255)
EO_COLOR = (80, 169, 255, 255)
AOI_COLOR = (250, 204, 21, 255)
ACCESS_COLOR = (245, 158, 11, 210)
SCHEDULE_COLOR = (52, 211, 153, 255)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Czas sceny Cesium musi zawierać strefę czasową")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _interval(start_utc: datetime, end_utc: datetime) -> str:
    return f"{_iso(start_utc)}/{_iso(end_utc)}"


def _rgba(values: Sequence[int]) -> dict[str, list[int]]:
    return {"rgba": [int(value) for value in values]}


def geometry_centroid(geometry: TargetGeometry) -> tuple[float, float]:
    """Zwraca reprezentatywny punkt geometrii WGS84."""

    if isinstance(geometry, PointGeometry):
        return geometry.coordinates

    ring = geometry.coordinates[0][:-1]
    if not ring:
        raise ValueError("Polygon nie zawiera wierzchołków")
    longitude = sum(point[0] for point in ring) / len(ring)
    latitude = sum(point[1] for point in ring) / len(ring)
    return longitude, latitude


def _family_color(family: SatelliteFamily) -> tuple[int, int, int, int]:
    if family == SatelliteFamily.ICEYE:
        return SAR_COLOR
    return EO_COLOR


def _satellite_description(track: SatelliteGroundTrack) -> str:
    satellite = track.satellite
    family = (
        "ICEYE SAR" if satellite.family == SatelliteFamily.ICEYE else "Pléiades Neo EO"
    )
    return (
        "<table>"
        f"<tr><th>Slot</th><td>{html.escape(satellite.slot_id)}</td></tr>"
        f"<tr><th>Rodzina</th><td>{family}</td></tr>"
        f"<tr><th>Obiekt</th><td>{html.escape(satellite.record.object_name)}</td></tr>"
        f"<tr><th>NORAD</th><td>{satellite.record.norad_cat_id}</td></tr>"
        f"<tr><th>Epoka OMM</th><td>{html.escape(_iso(satellite.record.epoch_utc))}</td></tr>"
        "</table>"
    )


def _track_packet(
    track: SatelliteGroundTrack,
    *,
    show_orbit_3d: bool,
) -> dict[str, Any]:
    if not track.states:
        raise ValueError(f"Ślad {track.satellite.slot_id} nie zawiera stanów")

    start_utc = track.states[0].timestamp_utc
    end_utc = track.states[-1].timestamp_utc
    epoch = _utc(start_utc)
    samples: list[float] = []
    for state in track.states:
        offset = (_utc(state.timestamp_utc) - epoch).total_seconds()
        samples.extend(
            [
                float(offset),
                float(state.longitude_deg),
                float(state.latitude_deg),
                float(state.altitude_km * 1000.0),
            ]
        )

    color = _family_color(track.satellite.family)
    family_name = (
        "ICEYE SAR"
        if track.satellite.family == SatelliteFamily.ICEYE
        else "Pléiades Neo EO"
    )
    packet: dict[str, Any] = {
        "id": f"satellite-{track.satellite.slot_id}",
        "name": f"{track.satellite.slot_id} · {family_name}",
        "availability": _interval(start_utc, end_utc),
        "description": _satellite_description(track),
        "position": {
            "epoch": _iso(epoch),
            "cartographicDegrees": samples,
            "interpolationAlgorithm": "LINEAR",
            "interpolationDegree": 1,
            "forwardExtrapolationType": "HOLD",
            "backwardExtrapolationType": "HOLD",
        },
        "point": {
            "pixelSize": 14,
            "color": _rgba(color),
            "outlineColor": _rgba((255, 255, 255, 245)),
            "outlineWidth": 2,
        },
        "label": {
            "text": track.satellite.slot_id,
            "font": "700 17px system-ui, sans-serif",
            "fillColor": _rgba((255, 255, 255, 255)),
            "outlineColor": _rgba((8, 15, 28, 255)),
            "outlineWidth": 4,
            "style": "FILL_AND_OUTLINE",
            "pixelOffset": {"cartesian2": [18, -22]},
            "showBackground": True,
            "backgroundColor": _rgba((8, 15, 28, 190)),
            "backgroundPadding": {"cartesian2": [8, 5]},
            "scaleByDistance": {"nearFarScalar": [1.0e6, 1.0, 2.5e7, 0.55]},
        },
    }
    if show_orbit_3d:
        packet["path"] = {
            "show": True,
            "width": 3,
            "leadTime": max(1.0, (end_utc - start_utc).total_seconds()),
            "trailTime": max(1.0, (end_utc - start_utc).total_seconds()),
            "resolution": 60,
            "material": {"solidColor": {"color": _rgba(color)}},
        }
    return packet


def _split_ground_track_states(
    states: Sequence[PropagatedState],
) -> list[list[PropagatedState]]:
    """Dzieli ślad przy antymeridianie, aby uniknąć linii przez pół globu."""

    segments: list[list[PropagatedState]] = []
    current: list[PropagatedState] = []
    previous_longitude: float | None = None
    for state in states:
        if (
            previous_longitude is not None
            and abs(state.longitude_deg - previous_longitude) > 180.0
            and current
        ):
            segments.append(current)
            current = []
        current.append(state)
        previous_longitude = state.longitude_deg
    if current:
        segments.append(current)
    return segments


def _ground_track_packets(
    track: SatelliteGroundTrack,
) -> list[dict[str, Any]]:
    if not track.states:
        return []

    color = _family_color(track.satellite.family)
    ground_color = (color[0], color[1], color[2], 190)
    packets: list[dict[str, Any]] = []
    for index, segment in enumerate(_split_ground_track_states(track.states), 1):
        if len(segment) < 2:
            continue
        coordinates: list[float] = []
        for state in segment:
            coordinates.extend(
                [
                    float(state.longitude_deg),
                    float(state.latitude_deg),
                    25000.0,
                ]
            )
        packets.append(
            {
                "id": f"groundtrack-{track.satellite.slot_id}-{index:02d}",
                "name": f"Ground track · {track.satellite.slot_id}",
                "description": (
                    "Rzut propagowanej trajektorii satelity na elipsoidę "
                    "WGS84. Linia ma charakter modelowy i wynika z OMM/SGP4."
                ),
                "polyline": {
                    "positions": {"cartographicDegrees": coordinates},
                    "width": 4,
                    "arcType": "GEODESIC",
                    "clampToGround": False,
                    "material": {
                        "polylineGlow": {
                            "color": _rgba(ground_color),
                            "glowPower": 0.16,
                            "taperPower": 0.8,
                        }
                    },
                },
            }
        )

    epoch = _utc(track.states[0].timestamp_utc)
    samples: list[float] = []
    for state in track.states:
        offset = (_utc(state.timestamp_utc) - epoch).total_seconds()
        samples.extend(
            [
                float(offset),
                float(state.longitude_deg),
                float(state.latitude_deg),
                30000.0,
            ]
        )
    packets.append(
        {
            "id": f"subsatellite-{track.satellite.slot_id}",
            "name": f"Punkt podsatelitarny · {track.satellite.slot_id}",
            "availability": _interval(
                track.states[0].timestamp_utc,
                track.states[-1].timestamp_utc,
            ),
            "position": {
                "epoch": _iso(epoch),
                "cartographicDegrees": samples,
                "interpolationAlgorithm": "LINEAR",
                "interpolationDegree": 1,
            },
            "point": {
                "pixelSize": 9,
                "color": _rgba(ground_color),
                "outlineColor": _rgba((255, 255, 255, 235)),
                "outlineWidth": 2,
                "heightReference": "RELATIVE_TO_GROUND",
            },
        }
    )
    return packets


def _request_description(request: ObservationRequest) -> str:
    sensor_types = ", ".join(sensor.value for sensor in request.requested_sensor_types)
    return (
        "<table>"
        f"<tr><th>Zlecenie</th><td>{html.escape(request.request_id)}</td></tr>"
        f"<tr><th>Nazwa</th><td>{html.escape(request.name)}</td></tr>"
        f"<tr><th>Priorytet</th><td>{request.priority}</td></tr>"
        f"<tr><th>Sensory</th><td>{html.escape(sensor_types)}</td></tr>"
        f"<tr><th>Okno</th><td>{html.escape(_iso(request.earliest_start_utc))}<br>"
        f"{html.escape(_iso(request.latest_end_utc))}</td></tr>"
        "</table>"
    )


def _request_packet(request: ObservationRequest) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "id": f"aoi-{request.request_id}",
        "name": f"AOI · {request.request_id} · {request.name}",
        "description": _request_description(request),
    }
    if isinstance(request.geometry, PointGeometry):
        longitude, latitude = request.geometry.coordinates
        packet.update(
            {
                "position": {"cartographicDegrees": [longitude, latitude, 30000.0]},
                "point": {
                    "pixelSize": 16,
                    "color": _rgba(AOI_COLOR),
                    "outlineColor": _rgba((17, 24, 39, 255)),
                    "outlineWidth": 3,
                },
                "label": {
                    "text": request.request_id,
                    "font": "700 16px system-ui, sans-serif",
                    "fillColor": _rgba((255, 255, 255, 255)),
                    "outlineColor": _rgba((17, 24, 39, 255)),
                    "outlineWidth": 4,
                    "style": "FILL_AND_OUTLINE",
                    "pixelOffset": {"cartesian2": [18, -18]},
                },
            }
        )
        return packet

    coordinates: list[float] = []
    for longitude, latitude in request.geometry.coordinates[0]:
        coordinates.extend([longitude, latitude, 30000.0])
    packet["polygon"] = {
        "positions": {"cartographicDegrees": coordinates},
        "material": {"solidColor": {"color": _rgba((250, 204, 21, 72))}},
        "outline": True,
        "outlineColor": _rgba(AOI_COLOR),
        "perPositionHeight": True,
    }
    longitude, latitude = geometry_centroid(request.geometry)
    packet["position"] = {"cartographicDegrees": [longitude, latitude, 35000.0]}
    packet["label"] = {
        "text": request.request_id,
        "font": "700 16px system-ui, sans-serif",
        "fillColor": _rgba((255, 255, 255, 255)),
        "outlineColor": _rgba((17, 24, 39, 255)),
        "outlineWidth": 4,
        "style": "FILL_AND_OUTLINE",
        "showBackground": True,
        "backgroundColor": _rgba((17, 24, 39, 185)),
        "backgroundPadding": {"cartesian2": [7, 4]},
    }
    return packet


def _nearest_state(
    track: SatelliteGroundTrack,
    timestamp_utc: datetime,
) -> PropagatedState | None:
    if not track.states:
        return None
    target = _utc(timestamp_utc)
    return min(
        track.states,
        key=lambda state: abs((_utc(state.timestamp_utc) - target).total_seconds()),
    )


def _mode_footprint_axes_m(
    *,
    family: SatelliteFamily,
    mode_id: str,
) -> tuple[float, float] | None:
    profile = (
        ICEYE_PUBLIC_PROFILE
        if family == SatelliteFamily.ICEYE
        else PLEIADES_NEO_PUBLIC_PROFILE
    )
    try:
        mode = profile.get_mode(mode_id)
    except KeyError:
        return None
    semi_major = max(100.0, mode.nominal_scene_length_km * 500.0)
    semi_minor = max(100.0, mode.nominal_scene_width_km * 500.0)
    return semi_major, semi_minor


def _access_packets(
    access_result: AccessCalculationResult,
    requests_by_id: dict[str, ObservationRequest],
    *,
    show_footprints: bool,
) -> list[dict[str, Any]]:
    request = requests_by_id.get(access_result.request_id)
    if request is None:
        return []
    target_longitude, target_latitude = geometry_centroid(request.geometry)
    packets: list[dict[str, Any]] = []
    for window in access_result.windows:
        if not window.path:
            continue
        peak = min(
            window.path,
            key=lambda point: abs(
                (_utc(point.timestamp_utc) - _utc(window.peak_utc)).total_seconds()
            ),
        )
        packet: dict[str, Any] = {
            "id": f"access-{window.window_id}",
            "name": (f"Okno dostępu · {window.satellite_id} · {window.mode_name}"),
            "availability": _interval(window.start_utc, window.end_utc),
            "description": (
                "<table>"
                f"<tr><th>Okno</th><td>{html.escape(window.window_id)}</td></tr>"
                f"<tr><th>Satelita</th><td>{html.escape(window.satellite_id)}</td></tr>"
                f"<tr><th>Tryb</th><td>{html.escape(window.mode_name)}</td></tr>"
                f"<tr><th>Pokrycie</th><td>{window.coverage_ratio:.1%}</td></tr>"
                f"<tr><th>Off-nadir</th><td>{window.minimum_off_nadir_deg:.1f}–"
                f"{window.maximum_off_nadir_deg:.1f}°</td></tr>"
                "</table>"
            ),
            "polyline": {
                "positions": {
                    "cartographicDegrees": [
                        peak.satellite_longitude_deg,
                        peak.satellite_latitude_deg,
                        peak.satellite_altitude_km * 1000.0,
                        target_longitude,
                        target_latitude,
                        30000.0,
                    ]
                },
                "width": 3,
                "arcType": "NONE",
                "material": {
                    "polylineGlow": {
                        "color": _rgba(ACCESS_COLOR),
                        "glowPower": 0.2,
                        "taperPower": 0.6,
                    }
                },
            },
            "position": {
                "cartographicDegrees": [
                    target_longitude,
                    target_latitude,
                    35000.0,
                ]
            },
            "point": {
                "pixelSize": 11,
                "color": _rgba(ACCESS_COLOR),
                "outlineColor": _rgba((255, 255, 255, 230)),
                "outlineWidth": 2,
            },
        }
        if show_footprints:
            footprint_axes = _mode_footprint_axes_m(
                family=window.family,
                mode_id=window.mode_id,
            )
            if footprint_axes is not None:
                semi_major, semi_minor = footprint_axes
                packet["ellipse"] = {
                    "semiMajorAxis": semi_major,
                    "semiMinorAxis": semi_minor,
                    "height": 30000.0,
                    "material": {"solidColor": {"color": _rgba((245, 158, 11, 44))}},
                    "outline": True,
                    "outlineColor": _rgba(ACCESS_COLOR),
                    "outlineWidth": 2,
                }
        packets.append(packet)
    return packets


def _schedule_packets(
    planning_result: PlanningResult,
    tracks_by_slot: dict[str, SatelliteGroundTrack],
    requests_by_id: dict[str, ObservationRequest],
    *,
    scene_start_utc: datetime,
    scene_end_utc: datetime,
) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for entry in planning_result.schedule.active_entries:
        if entry.end_utc < scene_start_utc or entry.start_utc > scene_end_utc:
            continue
        track = tracks_by_slot.get(entry.satellite_id)
        request = requests_by_id.get(entry.request_id)
        if track is None or request is None:
            continue
        midpoint = entry.start_utc + (entry.end_utc - entry.start_utc) / 2
        state = _nearest_state(track, midpoint)
        if state is None:
            continue
        target_longitude, target_latitude = geometry_centroid(request.geometry)
        packets.append(
            {
                "id": f"schedule-{entry.entry_id}",
                "name": (
                    f"Zaplanowana akwizycja · {entry.satellite_id} · {entry.request_id}"
                ),
                "availability": _interval(entry.start_utc, entry.end_utc),
                "description": (
                    "<table>"
                    f"<tr><th>Wpis</th><td>{html.escape(entry.entry_id)}</td></tr>"
                    f"<tr><th>Zlecenie</th><td>{html.escape(entry.request_id)}</td></tr>"
                    f"<tr><th>Satelita</th><td>{html.escape(entry.satellite_id)}</td></tr>"
                    f"<tr><th>Tryb</th><td>{html.escape(entry.mode_id)}</td></tr>"
                    f"<tr><th>Status</th><td>{html.escape(entry.status.value)}</td></tr>"
                    "</table>"
                ),
                "polyline": {
                    "positions": {
                        "cartographicDegrees": [
                            state.longitude_deg,
                            state.latitude_deg,
                            state.altitude_km * 1000.0,
                            target_longitude,
                            target_latitude,
                            30000.0,
                        ]
                    },
                    "width": 6,
                    "arcType": "NONE",
                    "material": {
                        "polylineGlow": {
                            "color": _rgba(SCHEDULE_COLOR),
                            "glowPower": 0.35,
                            "taperPower": 0.7,
                        }
                    },
                },
                "position": {
                    "cartographicDegrees": [
                        target_longitude,
                        target_latitude,
                        35000.0,
                    ]
                },
                "point": {
                    "pixelSize": 15,
                    "color": _rgba(SCHEDULE_COLOR),
                    "outlineColor": _rgba((255, 255, 255, 255)),
                    "outlineWidth": 3,
                },
                "label": {
                    "text": f"PLAN {entry.satellite_id}",
                    "font": "700 15px system-ui, sans-serif",
                    "fillColor": _rgba((255, 255, 255, 255)),
                    "outlineColor": _rgba((5, 46, 22, 255)),
                    "outlineWidth": 4,
                    "style": "FILL_AND_OUTLINE",
                    "pixelOffset": {"cartesian2": [18, -18]},
                },
            }
        )
    return packets


@dataclass(frozen=True, slots=True)
class CesiumScene:
    """Gotowy zestaw CZML oraz metadane widoku 3D."""

    packets: tuple[dict[str, Any], ...]
    start_utc: datetime
    end_utc: datetime
    satellite_count: int
    request_count: int
    access_window_count: int
    scheduled_acquisition_count: int

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            list(self.packets),
            ensure_ascii=False,
            indent=indent,
        )


def build_cesium_scene(
    *,
    tracks: Iterable[SatelliteGroundTrack],
    requests: Iterable[ObservationRequest] = (),
    access_result: AccessCalculationResult | None = None,
    planning_result: PlanningResult | None = None,
    show_aoi: bool = True,
    show_orbits_3d: bool = False,
    show_ground_tracks: bool = True,
    show_access_windows: bool = True,
    show_footprints: bool = True,
    show_schedule: bool = True,
) -> CesiumScene:
    """Buduje scenę 3D z orbitami, AOI, oknami i harmonogramem."""

    track_list = [track for track in tracks if track.states]
    if not track_list:
        raise ValueError("Scena 3D wymaga co najmniej jednego śladu satelity")

    start_utc = min(track.states[0].timestamp_utc for track in track_list)
    end_utc = max(track.states[-1].timestamp_utc for track in track_list)
    if start_utc >= end_utc:
        raise ValueError("Horyzont sceny 3D musi mieć dodatnią długość")

    request_list = list(requests)
    requests_by_id = {request.request_id: request for request in request_list}
    tracks_by_slot = {track.satellite.slot_id: track for track in track_list}

    duration_s = max(1.0, (end_utc - start_utc).total_seconds())
    multiplier = max(1, min(300, int(duration_s / 120.0)))
    packets: list[dict[str, Any]] = [
        {
            "id": "document",
            "name": "Satellite Acquisition Planner · publiczna scena 3D",
            "version": "1.0",
            "clock": {
                "interval": _interval(start_utc, end_utc),
                "currentTime": _iso(start_utc),
                "multiplier": multiplier,
                "range": "LOOP_STOP",
                "step": "SYSTEM_CLOCK_MULTIPLIER",
            },
        }
    ]
    packets.extend(
        _track_packet(track, show_orbit_3d=show_orbits_3d) for track in track_list
    )
    if show_ground_tracks:
        for track in track_list:
            packets.extend(_ground_track_packets(track))

    if show_aoi:
        packets.extend(_request_packet(request) for request in request_list)

    access_count = 0
    if show_access_windows and access_result is not None:
        access_packets = _access_packets(
            access_result,
            requests_by_id,
            show_footprints=show_footprints,
        )
        packets.extend(access_packets)
        access_count = len(access_packets)

    scheduled_count = 0
    if show_schedule and planning_result is not None:
        schedule_packets = _schedule_packets(
            planning_result,
            tracks_by_slot,
            requests_by_id,
            scene_start_utc=start_utc,
            scene_end_utc=end_utc,
        )
        packets.extend(schedule_packets)
        scheduled_count = len(schedule_packets)

    return CesiumScene(
        packets=tuple(packets),
        start_utc=_utc(start_utc),
        end_utc=_utc(end_utc),
        satellite_count=len(track_list),
        request_count=len(request_list) if show_aoi else 0,
        access_window_count=access_count,
        scheduled_acquisition_count=scheduled_count,
    )
