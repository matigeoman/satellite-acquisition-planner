from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.models.enums import OrbitSourceType, OrbitType, ReferenceFrame
from app.models.orbit import OrbitDefinition


def valid_orbit_data() -> dict:
    return {
        "orbit_id": "ORB-SAR-01",
        "name": "Nominalna orbita podkonstelacji SAR",
        "orbit_type": "CIRCULAR_SSO",
        "altitude_km": 550.0,
        "inclination_deg": 97.6,
        "eccentricity": 0.0,
        "raan_deg": 370.0,
        "argument_of_perigee_deg": 0.0,
        "epoch_utc": "2026-07-15T00:00:00Z",
        "reference_frame": "J2000",
        "is_sun_synchronous": True,
        "source_type": "MODEL",
        "source_reference": None,
        "notes": "Modelowa orbita SAR.",
    }


def test_valid_orbit_is_created() -> None:
    orbit = OrbitDefinition(**valid_orbit_data())

    assert orbit.orbit_id == "ORB-SAR-01"
    assert orbit.orbit_type == OrbitType.CIRCULAR_SSO
    assert orbit.reference_frame == ReferenceFrame.J2000
    assert orbit.source_type == OrbitSourceType.MODEL


def test_angle_is_normalized() -> None:
    orbit = OrbitDefinition(**valid_orbit_data())

    assert orbit.raan_deg == pytest.approx(10.0)


def test_epoch_is_in_utc() -> None:
    orbit = OrbitDefinition(**valid_orbit_data())

    assert orbit.epoch_utc.utcoffset() == timedelta(0)


def test_invalid_orbit_id_is_rejected() -> None:
    data = valid_orbit_data()
    data["orbit_id"] = "orbit sar 01"

    with pytest.raises(ValidationError):
        OrbitDefinition(**data)


def test_naive_datetime_is_rejected() -> None:
    data = valid_orbit_data()
    data["epoch_utc"] = "2026-07-15T00:00:00"

    with pytest.raises(ValidationError):
        OrbitDefinition(**data)


def test_large_eccentricity_is_rejected_for_circular_orbit() -> None:
    data = valid_orbit_data()
    data["eccentricity"] = 0.1

    with pytest.raises(ValidationError):
        OrbitDefinition(**data)


def test_public_data_requires_source_reference() -> None:
    data = valid_orbit_data()
    data["source_type"] = "PUBLIC_DATA"
    data["source_reference"] = None

    with pytest.raises(ValidationError):
        OrbitDefinition(**data)


def test_unknown_field_is_rejected() -> None:
    data = valid_orbit_data()
    data["unknown_field"] = 123

    with pytest.raises(ValidationError):
        OrbitDefinition(**data)