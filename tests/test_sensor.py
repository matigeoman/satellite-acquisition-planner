import pytest
from pydantic import ValidationError

from app.models.enums import (
    FrequencyBand,
    LookSideCapability,
    SensorType,
)
from app.models.sensor import Sensor


def valid_sar_mode_data() -> dict:
    return {
        "mode_id": "MODE-SAR-HR",
        "name": "SAR High Resolution",
        "sensor_type": "SAR",
        "mode_category": "SPOTLIGHT",
        "product_type": "SAR_IMAGE",
        "nominal_resolution_m": 0.25,
        "nominal_scene_width_km": 5.0,
        "nominal_scene_length_km": 5.0,
        "min_acquisition_duration_s": 20.0,
        "max_acquisition_duration_s": 60.0,
        "data_rate_mb_s": 25.0,
        "max_off_nadir_deg": 45.0,
        "min_incidence_angle_deg": 20.0,
        "max_incidence_angle_deg": 45.0,
        "polarizations": ["VV"],
        "spectral_bands": None,
        "quality_factor": 1.0,
        "is_active": True,
        "notes": None,
    }


def valid_optical_mode_data() -> dict:
    return {
        "mode_id": "MODE-OPT-PAN",
        "name": "Optical Panchromatic",
        "sensor_type": "OPTICAL",
        "mode_category": "PUSHBROOM",
        "product_type": "PANCHROMATIC",
        "nominal_resolution_m": 0.3,
        "nominal_scene_width_km": 14.0,
        "nominal_scene_length_km": 14.0,
        "min_acquisition_duration_s": 5.0,
        "max_acquisition_duration_s": 60.0,
        "data_rate_mb_s": 18.0,
        "max_off_nadir_deg": 45.0,
        "min_incidence_angle_deg": None,
        "max_incidence_angle_deg": None,
        "polarizations": None,
        "spectral_bands": ["PAN"],
        "quality_factor": 1.0,
        "is_active": True,
        "notes": None,
    }


def valid_sar_sensor_data() -> dict:
    return {
        "sensor_id": "SENSOR-SAR-X",
        "name": "Modelowy sensor SAR pasma X",
        "sensor_type": "SAR",
        "imaging_modes": [valid_sar_mode_data()],
        "frequency_band": "X",
        "cloud_sensitive": False,
        "daylight_required": False,
        "minimum_sun_elevation_deg": None,
        "default_max_cloud_cover": None,
        "look_side_capability": "BOTH",
        "warmup_time_s": 10.0,
        "cooldown_time_s": 20.0,
        "maximum_continuous_acquisition_s": 180.0,
        "is_active": True,
        "source_type": "MODEL",
        "source_reference": None,
        "notes": None,
    }


def valid_optical_sensor_data() -> dict:
    return {
        "sensor_id": "SENSOR-EO-HR",
        "name": "Modelowy sensor optyczny",
        "sensor_type": "OPTICAL",
        "imaging_modes": [valid_optical_mode_data()],
        "frequency_band": None,
        "cloud_sensitive": True,
        "daylight_required": True,
        "minimum_sun_elevation_deg": 10.0,
        "default_max_cloud_cover": 0.3,
        "look_side_capability": "BOTH",
        "warmup_time_s": 5.0,
        "cooldown_time_s": 10.0,
        "maximum_continuous_acquisition_s": 120.0,
        "is_active": True,
        "source_type": "MODEL",
        "source_reference": None,
        "notes": None,
    }


def test_valid_sar_sensor_is_created() -> None:
    sensor = Sensor(**valid_sar_sensor_data())

    assert sensor.sensor_type == SensorType.SAR
    assert sensor.frequency_band == FrequencyBand.X
    assert sensor.look_side_capability == LookSideCapability.BOTH
    assert len(sensor.imaging_modes) == 1


def test_valid_optical_sensor_is_created() -> None:
    sensor = Sensor(**valid_optical_sensor_data())

    assert sensor.sensor_type == SensorType.OPTICAL
    assert sensor.default_max_cloud_cover == pytest.approx(0.3)


def test_sar_sensor_requires_frequency_band() -> None:
    data = valid_sar_sensor_data()
    data["frequency_band"] = None

    with pytest.raises(ValidationError):
        Sensor(**data)


def test_sar_sensor_rejects_cloud_limit() -> None:
    data = valid_sar_sensor_data()
    data["default_max_cloud_cover"] = 0.3

    with pytest.raises(ValidationError):
        Sensor(**data)


def test_optical_sensor_rejects_frequency_band() -> None:
    data = valid_optical_sensor_data()
    data["frequency_band"] = "X"

    with pytest.raises(ValidationError):
        Sensor(**data)


def test_optical_sensor_requires_daylight() -> None:
    data = valid_optical_sensor_data()
    data["daylight_required"] = False

    with pytest.raises(ValidationError):
        Sensor(**data)


def test_sensor_rejects_mode_type_mismatch() -> None:
    data = valid_sar_sensor_data()
    data["imaging_modes"] = [valid_optical_mode_data()]

    with pytest.raises(ValidationError):
        Sensor(**data)


def test_sensor_rejects_duplicate_mode_ids() -> None:
    data = valid_sar_sensor_data()
    data["imaging_modes"] = [
        valid_sar_mode_data(),
        valid_sar_mode_data(),
    ]

    with pytest.raises(ValidationError):
        Sensor(**data)


def test_sensor_requires_active_mode() -> None:
    data = valid_sar_sensor_data()
    data["imaging_modes"][0]["is_active"] = False

    with pytest.raises(ValidationError):
        Sensor(**data)


def test_mode_duration_cannot_exceed_sensor_limit() -> None:
    data = valid_sar_sensor_data()
    data["maximum_continuous_acquisition_s"] = 30.0

    with pytest.raises(ValidationError):
        Sensor(**data)


def test_public_data_requires_source_reference() -> None:
    data = valid_sar_sensor_data()
    data["source_type"] = "PUBLIC_DATA"
    data["source_reference"] = None

    with pytest.raises(ValidationError):
        Sensor(**data)


def test_unknown_field_is_rejected() -> None:
    data = valid_sar_sensor_data()
    data["unknown_field"] = 123

    with pytest.raises(ValidationError):
        Sensor(**data)