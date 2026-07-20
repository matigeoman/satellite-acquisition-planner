from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping


class SatelliteFamily(StrEnum):
    """Rodzina satelitów śledzona przez moduł publicznych orbit."""

    ICEYE = "ICEYE"
    PLEIADES_NEO = "PLEIADES_NEO"


class OrbitDataFormat(StrEnum):
    """Format danych pobieranych z serwisu CelesTrak."""

    OMM_JSON = "OMM_JSON"


def _as_float(payload: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = payload.get(key, default)
    if value in (None, ""):
        return float(default)
    return float(value)


def _as_int(payload: Mapping[str, Any], key: str, default: int = 0) -> int:
    value = payload.get(key, default)
    if value in (None, ""):
        return int(default)
    return int(value)


def _parse_epoch(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Rekord OMM nie zawiera poprawnego pola EPOCH")

    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class PublicOrbitRecord:
    """Znormalizowany rekord GP/OMM pobrany z CelesTrak."""

    object_name: str
    object_id: str
    norad_cat_id: int
    epoch_utc: datetime
    mean_motion_rev_per_day: float
    eccentricity: float
    inclination_deg: float
    raan_deg: float
    argument_of_pericenter_deg: float
    mean_anomaly_deg: float
    bstar: float
    mean_motion_dot: float
    mean_motion_ddot: float
    element_set_no: int
    rev_at_epoch: int
    raw_omm: Mapping[str, Any]

    @classmethod
    def from_omm(cls, payload: Mapping[str, Any]) -> "PublicOrbitRecord":
        """Tworzy rekord domenowy z pól OMM JSON."""

        name = str(payload.get("OBJECT_NAME", "")).strip()
        if not name:
            raise ValueError("Rekord OMM nie zawiera OBJECT_NAME")

        norad_cat_id = _as_int(payload, "NORAD_CAT_ID")
        if norad_cat_id <= 0:
            raise ValueError("Rekord OMM nie zawiera poprawnego NORAD_CAT_ID")

        mean_motion = _as_float(payload, "MEAN_MOTION")
        if mean_motion <= 0:
            raise ValueError("Rekord OMM nie zawiera poprawnego MEAN_MOTION")

        eccentricity = _as_float(payload, "ECCENTRICITY")
        if not 0 <= eccentricity < 1:
            raise ValueError("ECCENTRICITY musi należeć do zakresu [0, 1)")

        raw = dict(payload)
        return cls(
            object_name=name,
            object_id=str(payload.get("OBJECT_ID", "")).strip(),
            norad_cat_id=norad_cat_id,
            epoch_utc=_parse_epoch(payload.get("EPOCH")),
            mean_motion_rev_per_day=mean_motion,
            eccentricity=eccentricity,
            inclination_deg=_as_float(payload, "INCLINATION"),
            raan_deg=_as_float(payload, "RA_OF_ASC_NODE"),
            argument_of_pericenter_deg=_as_float(
                payload,
                "ARG_OF_PERICENTER",
            ),
            mean_anomaly_deg=_as_float(payload, "MEAN_ANOMALY"),
            bstar=_as_float(payload, "BSTAR"),
            mean_motion_dot=_as_float(payload, "MEAN_MOTION_DOT"),
            mean_motion_ddot=_as_float(payload, "MEAN_MOTION_DDOT"),
            element_set_no=_as_int(payload, "ELEMENT_SET_NO"),
            rev_at_epoch=_as_int(payload, "REV_AT_EPOCH"),
            raw_omm=raw,
        )

    @property
    def orbital_period_minutes(self) -> float:
        return 1440.0 / self.mean_motion_rev_per_day

    def to_omm_fields(self) -> dict[str, Any]:
        """Zwraca kompletny słownik wejściowy dla ``sgp4.omm.initialize``."""

        fields = dict(self.raw_omm)
        fields.setdefault("OBJECT_NAME", self.object_name)
        fields.setdefault("OBJECT_ID", self.object_id)
        fields.setdefault("CENTER_NAME", "EARTH")
        fields.setdefault("REF_FRAME", "TEME")
        fields.setdefault("TIME_SYSTEM", "UTC")
        fields.setdefault("MEAN_ELEMENT_THEORY", "SGP4")
        fields.setdefault("CLASSIFICATION_TYPE", "U")
        fields.setdefault("EPHEMERIS_TYPE", 0)
        fields.setdefault("ELEMENT_SET_NO", self.element_set_no)
        fields.setdefault("REV_AT_EPOCH", self.rev_at_epoch)
        fields.setdefault("MEAN_MOTION_DOT", self.mean_motion_dot)
        fields.setdefault("MEAN_MOTION_DDOT", self.mean_motion_ddot)
        fields.setdefault("BSTAR", self.bstar)
        return fields

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_name": self.object_name,
            "object_id": self.object_id,
            "norad_cat_id": self.norad_cat_id,
            "epoch_utc": self.epoch_utc.isoformat(),
            "mean_motion_rev_per_day": self.mean_motion_rev_per_day,
            "orbital_period_minutes": self.orbital_period_minutes,
            "eccentricity": self.eccentricity,
            "inclination_deg": self.inclination_deg,
            "raan_deg": self.raan_deg,
            "argument_of_pericenter_deg": self.argument_of_pericenter_deg,
            "mean_anomaly_deg": self.mean_anomaly_deg,
        }


@dataclass(frozen=True, slots=True)
class CelestrakQueryResult:
    """Wynik jednego zapytania wraz z metadanymi cache."""

    query_name: str
    records: tuple[PublicOrbitRecord, ...]
    fetched_at_utc: datetime
    request_url: str
    from_cache: bool
    is_stale: bool
    warning: str | None = None

    @property
    def age_seconds(self) -> float:
        return max(
            0.0,
            (datetime.now(timezone.utc) - self.fetched_at_utc).total_seconds(),
        )


@dataclass(frozen=True, slots=True)
class TrackedSatellite:
    """Publiczny obiekt orbitalny przypisany do slotu planera."""

    slot_id: str
    family: SatelliteFamily
    record: PublicOrbitRecord

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "family": self.family.value,
            **self.record.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PropagatedState:
    """Pozycja jednego satelity w określonej chwili."""

    timestamp_utc: datetime
    latitude_deg: float
    longitude_deg: float
    altitude_km: float
    teme_position_km: tuple[float, float, float]
    teme_velocity_km_s: tuple[float, float, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "altitude_km": self.altitude_km,
            "teme_position_km": list(self.teme_position_km),
            "teme_velocity_km_s": list(self.teme_velocity_km_s),
        }


@dataclass(frozen=True, slots=True)
class SatelliteGroundTrack:
    """Szereg propagowanych stanów jednej jednostki."""

    satellite: TrackedSatellite
    states: tuple[PropagatedState, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "satellite": self.satellite.to_dict(),
            "states": [state.to_dict() for state in self.states],
        }
