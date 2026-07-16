from __future__ import annotations

from datetime import datetime, timezone

from app.catalogs.models import (
    ParameterOrigin,
    ParameterSource,
    PublicMissionProfile,
)
from app.models.enums import (
    LookSideCapability,
    ModeCategory,
    OrbitSourceType,
    OrbitType,
    ProductType,
    ReferenceFrame,
    SensorSourceType,
    SensorType,
)
from app.models.imaging import ImagingMode
from app.models.orbit import OrbitDefinition
from app.models.sensor import Sensor


PLEIADES_NEO_USER_GUIDE_REFERENCE = (
    "Airbus Defence and Space, Pléiades Neo User Guide, "
    "Early Version 3, October 2021"
)
PLEIADES_NEO_PUBLIC_PAGE = (
    "https://space-solutions.airbus.com/imagery/our-optical-and-radar-"
    "satellite-imagery/pleiades-neo/"
)


def _optical_mode(
    *,
    mode_id: str,
    name: str,
    product_type: ProductType,
    resolution_m: float,
    spectral_bands: list[str],
    quality_factor: float,
) -> ImagingMode:
    return ImagingMode(
        mode_id=mode_id,
        name=name,
        sensor_type=SensorType.OPTICAL,
        mode_category=ModeCategory.PUSHBROOM,
        product_type=product_type,
        nominal_resolution_m=resolution_m,
        nominal_scene_width_km=14.0,
        nominal_scene_length_km=14.0,
        min_acquisition_duration_s=5.0,
        max_acquisition_duration_s=150.0,
        data_rate_mb_s=150.0,
        max_off_nadir_deg=52.0,
        min_incidence_angle_deg=None,
        max_incidence_angle_deg=None,
        polarizations=None,
        spectral_bands=spectral_bands,
        quality_factor=quality_factor,
        notes=(
            "Rozdzielczość, pasma, szerokość pasa i kąt widzenia są "
            "publiczne. Czas 5–150 s oraz data_rate_mb_s=150 są "
            "jawnymi założeniami modelowymi do planowania."
        ),
    )


def build_pleiades_neo_public_profile() -> PublicMissionProfile:
    """Buduje publiczny profil dwóch dostępnych satelitów Pléiades Neo."""

    multispectral_bands = [
        "DEEP_BLUE",
        "BLUE",
        "GREEN",
        "RED",
        "RED_EDGE",
        "NIR",
    ]

    sensor = Sensor(
        sensor_id="SENSOR-EO-PLEIADES-NEO-PUBLIC",
        name="Pléiades Neo optical public profile",
        sensor_type=SensorType.OPTICAL,
        imaging_modes=[
            _optical_mode(
                mode_id="MODE-OPT-PLEIADES-NEO-PAN",
                name="Pléiades Neo Panchromatic",
                product_type=ProductType.PANCHROMATIC,
                resolution_m=0.3,
                spectral_bands=["PAN_450_800_NM"],
                quality_factor=0.98,
            ),
            _optical_mode(
                mode_id="MODE-OPT-PLEIADES-NEO-MS",
                name="Pléiades Neo Multispectral",
                product_type=ProductType.MULTISPECTRAL,
                resolution_m=1.2,
                spectral_bands=multispectral_bands,
                quality_factor=0.90,
            ),
            _optical_mode(
                mode_id="MODE-OPT-PLEIADES-NEO-PANSHARPENED",
                name="Pléiades Neo Pansharpened",
                product_type=ProductType.PANSHARPENED,
                resolution_m=0.3,
                spectral_bands=multispectral_bands,
                quality_factor=1.0,
            ),
        ],
        frequency_band=None,
        cloud_sensitive=True,
        daylight_required=True,
        minimum_sun_elevation_deg=10.0,
        default_max_cloud_cover=0.20,
        look_side_capability=LookSideCapability.BOTH,
        warmup_time_s=0.0,
        cooldown_time_s=0.0,
        maximum_continuous_acquisition_s=150.0,
        source_type=SensorSourceType.PUBLIC_DATA,
        source_reference=PLEIADES_NEO_PUBLIC_PAGE,
        notes=(
            "Próg zachmurzenia i minimalna elewacja Słońca są "
            "konfigurowalnymi założeniami modelu, nie gwarancją operatora."
        ),
    )

    orbit = OrbitDefinition(
        orbit_id="ORB-EO-PLEIADES-NEO-PUBLIC",
        name="Pléiades Neo public orbit template",
        orbit_type=OrbitType.CIRCULAR_SSO,
        altitude_km=620.0,
        inclination_deg=97.9,
        eccentricity=0.0,
        raan_deg=0.0,
        argument_of_perigee_deg=0.0,
        epoch_utc=datetime(2021, 1, 1, tzinfo=timezone.utc),
        reference_frame=ReferenceFrame.J2000,
        is_sun_synchronous=True,
        source_type=OrbitSourceType.MODEL,
        notes=(
            "Wysokość i inklinacja pochodzą z User Guide. RAAN, epoka "
            "i mimośród są szablonem; propagacja użyje aktualnego TLE/OMM."
        ),
    )

    return PublicMissionProfile(
        profile_id="PROFILE-PLEIADES-NEO-PUBLIC",
        name="Pléiades Neo public profile",
        operator="Airbus Defence and Space",
        description=(
            "Publiczny profil bardzo wysokiej rozdzielczości dla dwóch "
            "satelitów Pléiades Neo. Orbita zostanie później zastąpiona "
            "aktualnymi elementami GP/TLE."
        ),
        satellite_slots=2,
        satellite_labels=["Pléiades Neo 3", "Pléiades Neo 4"],
        orbit_template=orbit,
        sensor=sensor,
        product_sizes_by_mode={},
        parameter_sources=[
            ParameterSource(
                parameter_group="orbita, rozdzielczość, pasma i geometria",
                origin=ParameterOrigin.PUBLIC_DATA,
                reference=PLEIADES_NEO_USER_GUIDE_REFERENCE,
            ),
            ParameterSource(
                parameter_group=(
                    "czas akwizycji, szybkość danych, zachmurzenie i Słońce"
                ),
                origin=ParameterOrigin.MODEL_DERIVED,
                reference=PLEIADES_NEO_USER_GUIDE_REFERENCE,
                notes="Wartości jawne i konfigurowalne w aplikacji.",
            ),
            ParameterSource(
                parameter_group="orbita każdej jednostki",
                origin=ParameterOrigin.TLE_PENDING,
                reference="CelesTrak GP/OMM — etap propagacji SGP4",
            ),
        ],
    )


PLEIADES_NEO_PUBLIC_PROFILE = build_pleiades_neo_public_profile()
