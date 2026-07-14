import pytest
from pydantic import ValidationError

from app.models.enums import ModeCategory, ProductType, SensorType
from app.models.imaging import ImagingMode


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
        "polarizations": ["vv"],
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
        "spectral_bands": ["pan"],
        "quality_factor": 1.0,
        "is_active": True,
        "notes": None,
    }


def test_valid_sar_mode_is_created() -> None:
    mode = ImagingMode(**valid_sar_mode_data())

    assert mode.sensor_type == SensorType.SAR
    assert mode.mode_category == ModeCategory.SPOTLIGHT
    assert mode.product_type == ProductType.SAR_IMAGE


def test_polarizations_are_normalized() -> None:
    mode = ImagingMode(**valid_sar_mode_data())

    assert mode.polarizations == ["VV"]


def test_invalid_duration_range_is_rejected() -> None:
    data = valid_sar_mode_data()
    data["min_acquisition_duration_s"] = 80.0
    data["max_acquisition_duration_s"] = 60.0

    with pytest.raises(ValidationError):
        ImagingMode(**data)


def test_sar_mode_requires_incidence_angles() -> None:
    data = valid_sar_mode_data()
    data["min_incidence_angle_deg"] = None

    with pytest.raises(ValidationError):
        ImagingMode(**data)


def test_sar_mode_rejects_spectral_bands() -> None:
    data = valid_sar_mode_data()
    data["spectral_bands"] = ["RED"]

    with pytest.raises(ValidationError):
        ImagingMode(**data)


def test_invalid_sar_polarization_is_rejected() -> None:
    data = valid_sar_mode_data()
    data["polarizations"] = ["XX"]

    with pytest.raises(ValidationError):
        ImagingMode(**data)


def test_valid_optical_mode_is_created() -> None:
    mode = ImagingMode(**valid_optical_mode_data())

    assert mode.sensor_type == SensorType.OPTICAL
    assert mode.spectral_bands == ["PAN"]


def test_optical_mode_rejects_polarizations() -> None:
    data = valid_optical_mode_data()
    data["polarizations"] = ["VV"]

    with pytest.raises(ValidationError):
        ImagingMode(**data)


def test_optical_mode_rejects_sar_product() -> None:
    data = valid_optical_mode_data()
    data["product_type"] = "SAR_IMAGE"

    with pytest.raises(ValidationError):
        ImagingMode(**data)


def test_duplicate_spectral_bands_are_rejected() -> None:
    data = valid_optical_mode_data()
    data["spectral_bands"] = ["PAN", "pan"]

    with pytest.raises(ValidationError):
        ImagingMode(**data)


def test_unknown_field_is_rejected() -> None:
    data = valid_sar_mode_data()
    data["unknown_field"] = 123

    with pytest.raises(ValidationError):
        ImagingMode(**data)