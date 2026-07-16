import json
from pathlib import Path
from typing import Any


from _bootstrap import PROJECT_ROOT


from app.models.request_set import ObservationRequestSet


OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "example_requests.json"
)


def point(
    longitude: float,
    latitude: float,
) -> dict[str, Any]:
    return {
        "type": "Point",
        "coordinates": [
            longitude,
            latitude,
        ],
    }


def polygon(
    min_longitude: float,
    min_latitude: float,
    max_longitude: float,
    max_latitude: float,
) -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_longitude, min_latitude],
                [max_longitude, min_latitude],
                [max_longitude, max_latitude],
                [min_longitude, max_latitude],
                [min_longitude, min_latitude],
            ]
        ],
    }


def request(
    *,
    request_id: str,
    name: str,
    geometry: dict[str, Any],
    priority: int,
    earliest_start_utc: str,
    latest_end_utc: str,
    request_mode: str,
    sensor_types: list[str],
    max_resolution_m: float,
    minimum_coverage_ratio: float,
    max_cloud_cover: float | None,
    max_incidence_angle_deg: float | None,
    is_mandatory: bool = False,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "name": name,
        "geometry": geometry,
        "priority": priority,
        "earliest_start_utc": earliest_start_utc,
        "latest_end_utc": latest_end_utc,
        "request_mode": request_mode,
        "requested_sensor_types": sensor_types,
        "max_resolution_m": max_resolution_m,
        "minimum_coverage_ratio": minimum_coverage_ratio,
        "max_cloud_cover": max_cloud_cover,
        "max_incidence_angle_deg": max_incidence_angle_deg,
        "max_off_nadir_deg": 45.0,
        "status": "ACTIVE",
        "is_mandatory": is_mandatory,
        "external_reference": f"ORDER-{request_id}",
        "notes": None,
    }


def build_request_set() -> ObservationRequestSet:
    requests = [
        request(
            request_id="REQ-SAR-001",
            name="Pilna obserwacja SAR Warszawy",
            geometry=point(21.0122, 52.2297),
            priority=10,
            earliest_start_utc="2026-07-15T00:00:00Z",
            latest_end_utc="2026-07-15T06:00:00Z",
            request_mode="SINGLE",
            sensor_types=["SAR"],
            max_resolution_m=0.5,
            minimum_coverage_ratio=1.0,
            max_cloud_cover=None,
            max_incidence_angle_deg=45.0,
            is_mandatory=True,
        ),
        request(
            request_id="REQ-SAR-002",
            name="Obserwacja SAR Gdańska",
            geometry=point(18.6466, 54.3520),
            priority=8,
            earliest_start_utc="2026-07-15T01:00:00Z",
            latest_end_utc="2026-07-15T08:00:00Z",
            request_mode="SINGLE",
            sensor_types=["SAR"],
            max_resolution_m=1.0,
            minimum_coverage_ratio=1.0,
            max_cloud_cover=None,
            max_incidence_angle_deg=45.0,
        ),
        request(
            request_id="REQ-SAR-003",
            name="Obserwacja SAR Krakowa",
            geometry=point(19.9450, 50.0647),
            priority=7,
            earliest_start_utc="2026-07-15T02:00:00Z",
            latest_end_utc="2026-07-15T10:00:00Z",
            request_mode="SINGLE",
            sensor_types=["SAR"],
            max_resolution_m=1.0,
            minimum_coverage_ratio=1.0,
            max_cloud_cover=None,
            max_incidence_angle_deg=45.0,
        ),
        request(
            request_id="REQ-SAR-004",
            name="Obserwacja SAR Wrocławia",
            geometry=point(17.0385, 51.1079),
            priority=6,
            earliest_start_utc="2026-07-15T03:00:00Z",
            latest_end_utc="2026-07-15T11:00:00Z",
            request_mode="SINGLE",
            sensor_types=["SAR"],
            max_resolution_m=1.0,
            minimum_coverage_ratio=0.9,
            max_cloud_cover=None,
            max_incidence_angle_deg=45.0,
        ),
        request(
            request_id="REQ-SAR-005",
            name="Obserwacja SAR Poznania",
            geometry=point(16.9252, 52.4064),
            priority=5,
            earliest_start_utc="2026-07-15T04:00:00Z",
            latest_end_utc="2026-07-15T12:00:00Z",
            request_mode="SINGLE",
            sensor_types=["SAR"],
            max_resolution_m=3.0,
            minimum_coverage_ratio=0.9,
            max_cloud_cover=None,
            max_incidence_angle_deg=45.0,
        ),
        request(
            request_id="REQ-SAR-006",
            name="Obserwacja SAR Lublina",
            geometry=point(22.5684, 51.2465),
            priority=7,
            earliest_start_utc="2026-07-15T05:00:00Z",
            latest_end_utc="2026-07-15T13:00:00Z",
            request_mode="SINGLE",
            sensor_types=["SAR"],
            max_resolution_m=1.0,
            minimum_coverage_ratio=1.0,
            max_cloud_cover=None,
            max_incidence_angle_deg=45.0,
        ),
        request(
            request_id="REQ-SAR-007",
            name="Obserwacja SAR wybrzeża Bałtyku",
            geometry=polygon(17.7, 54.2, 19.3, 54.8),
            priority=9,
            earliest_start_utc="2026-07-15T06:00:00Z",
            latest_end_utc="2026-07-15T15:00:00Z",
            request_mode="SINGLE",
            sensor_types=["SAR"],
            max_resolution_m=3.0,
            minimum_coverage_ratio=0.9,
            max_cloud_cover=None,
            max_incidence_angle_deg=45.0,
        ),
        request(
            request_id="REQ-SAR-008",
            name="Obserwacja SAR Górnego Śląska",
            geometry=polygon(18.5, 49.9, 19.4, 50.5),
            priority=8,
            earliest_start_utc="2026-07-15T08:00:00Z",
            latest_end_utc="2026-07-15T18:00:00Z",
            request_mode="SINGLE",
            sensor_types=["SAR"],
            max_resolution_m=1.0,
            minimum_coverage_ratio=0.9,
            max_cloud_cover=None,
            max_incidence_angle_deg=45.0,
        ),
        request(
            request_id="REQ-EO-001",
            name="Pilna obserwacja optyczna Warszawy",
            geometry=point(21.0122, 52.2297),
            priority=10,
            earliest_start_utc="2026-07-15T06:00:00Z",
            latest_end_utc="2026-07-15T12:00:00Z",
            request_mode="SINGLE",
            sensor_types=["OPTICAL"],
            max_resolution_m=0.3,
            minimum_coverage_ratio=1.0,
            max_cloud_cover=0.2,
            max_incidence_angle_deg=None,
            is_mandatory=True,
        ),
        request(
            request_id="REQ-EO-002",
            name="Obserwacja optyczna Gdańska",
            geometry=point(18.6466, 54.3520),
            priority=8,
            earliest_start_utc="2026-07-15T07:00:00Z",
            latest_end_utc="2026-07-15T14:00:00Z",
            request_mode="SINGLE",
            sensor_types=["OPTICAL"],
            max_resolution_m=0.3,
            minimum_coverage_ratio=1.0,
            max_cloud_cover=0.3,
            max_incidence_angle_deg=None,
        ),
        request(
            request_id="REQ-EO-003",
            name="Obserwacja optyczna Krakowa",
            geometry=point(19.9450, 50.0647),
            priority=7,
            earliest_start_utc="2026-07-15T08:00:00Z",
            latest_end_utc="2026-07-15T15:00:00Z",
            request_mode="SINGLE",
            sensor_types=["OPTICAL"],
            max_resolution_m=0.3,
            minimum_coverage_ratio=1.0,
            max_cloud_cover=0.3,
            max_incidence_angle_deg=None,
        ),
        request(
            request_id="REQ-EO-004",
            name="Obserwacja optyczna Wrocławia",
            geometry=point(17.0385, 51.1079),
            priority=6,
            earliest_start_utc="2026-07-15T09:00:00Z",
            latest_end_utc="2026-07-15T16:00:00Z",
            request_mode="SINGLE",
            sensor_types=["OPTICAL"],
            max_resolution_m=1.2,
            minimum_coverage_ratio=0.9,
            max_cloud_cover=0.3,
            max_incidence_angle_deg=None,
        ),
        request(
            request_id="REQ-EO-005",
            name="Obserwacja optyczna Poznania",
            geometry=point(16.9252, 52.4064),
            priority=5,
            earliest_start_utc="2026-07-15T10:00:00Z",
            latest_end_utc="2026-07-15T17:00:00Z",
            request_mode="SINGLE",
            sensor_types=["OPTICAL"],
            max_resolution_m=1.2,
            minimum_coverage_ratio=0.9,
            max_cloud_cover=0.35,
            max_incidence_angle_deg=None,
        ),
        request(
            request_id="REQ-EO-006",
            name="Obserwacja optyczna Lublina",
            geometry=point(22.5684, 51.2465),
            priority=7,
            earliest_start_utc="2026-07-15T11:00:00Z",
            latest_end_utc="2026-07-15T18:00:00Z",
            request_mode="SINGLE",
            sensor_types=["OPTICAL"],
            max_resolution_m=0.3,
            minimum_coverage_ratio=1.0,
            max_cloud_cover=0.25,
            max_incidence_angle_deg=None,
        ),
        request(
            request_id="REQ-EO-007",
            name="Obserwacja optyczna Mazur",
            geometry=polygon(20.8, 53.5, 22.2, 54.3),
            priority=8,
            earliest_start_utc="2026-07-15T08:00:00Z",
            latest_end_utc="2026-07-15T16:00:00Z",
            request_mode="SINGLE",
            sensor_types=["OPTICAL"],
            max_resolution_m=1.2,
            minimum_coverage_ratio=0.85,
            max_cloud_cover=0.35,
            max_incidence_angle_deg=None,
        ),
        request(
            request_id="REQ-EO-008",
            name="Obserwacja optyczna Puszczy Białowieskiej",
            geometry=polygon(23.5, 52.5, 24.2, 53.1),
            priority=9,
            earliest_start_utc="2026-07-15T09:00:00Z",
            latest_end_utc="2026-07-15T17:00:00Z",
            request_mode="SINGLE",
            sensor_types=["OPTICAL"],
            max_resolution_m=0.3,
            minimum_coverage_ratio=0.9,
            max_cloud_cover=0.25,
            max_incidence_angle_deg=None,
        ),
        request(
            request_id="REQ-DUAL-OPT-001",
            name="Opcjonalna obserwacja podwójna aglomeracji warszawskiej",
            geometry=polygon(20.7, 52.0, 21.4, 52.5),
            priority=9,
            earliest_start_utc="2026-07-15T05:00:00Z",
            latest_end_utc="2026-07-15T20:00:00Z",
            request_mode="DUAL_OPTIONAL",
            sensor_types=["SAR", "OPTICAL"],
            max_resolution_m=1.0,
            minimum_coverage_ratio=0.9,
            max_cloud_cover=0.3,
            max_incidence_angle_deg=45.0,
        ),
        request(
            request_id="REQ-DUAL-OPT-002",
            name="Opcjonalna obserwacja podwójna Zatoki Gdańskiej",
            geometry=polygon(18.2, 54.2, 19.2, 54.8),
            priority=8,
            earliest_start_utc="2026-07-15T04:00:00Z",
            latest_end_utc="2026-07-15T22:00:00Z",
            request_mode="DUAL_OPTIONAL",
            sensor_types=["SAR", "OPTICAL"],
            max_resolution_m=1.2,
            minimum_coverage_ratio=0.85,
            max_cloud_cover=0.35,
            max_incidence_angle_deg=45.0,
        ),
        request(
            request_id="REQ-DUAL-REQ-001",
            name="Obowiązkowe monitorowanie obszaru powodziowego",
            geometry=polygon(20.0, 50.0, 21.2, 50.8),
            priority=10,
            earliest_start_utc="2026-07-15T00:00:00Z",
            latest_end_utc="2026-07-15T23:00:00Z",
            request_mode="DUAL_REQUIRED",
            sensor_types=["SAR", "OPTICAL"],
            max_resolution_m=1.0,
            minimum_coverage_ratio=0.9,
            max_cloud_cover=0.4,
            max_incidence_angle_deg=45.0,
            is_mandatory=True,
        ),
        request(
            request_id="REQ-DUAL-REQ-002",
            name="Obowiązkowe monitorowanie wschodniego odcinka granicy",
            geometry=polygon(22.8, 51.0, 24.0, 52.2),
            priority=10,
            earliest_start_utc="2026-07-15T00:00:00Z",
            latest_end_utc="2026-07-15T23:30:00Z",
            request_mode="DUAL_REQUIRED",
            sensor_types=["SAR", "OPTICAL"],
            max_resolution_m=1.0,
            minimum_coverage_ratio=0.9,
            max_cloud_cover=0.4,
            max_incidence_angle_deg=45.0,
            is_mandatory=True,
        ),
    ]

    return ObservationRequestSet(
        request_set_id="REQSET-PL-DEMO",
        name="Przykładowe dobowe zlecenia obserwacyjne",
        version="1.0.0",
        horizon_start_utc="2026-07-15T00:00:00Z",
        horizon_end_utc="2026-07-16T00:00:00Z",
        generated_at_utc="2026-07-14T20:00:00Z",
        requests=requests,
        notes=(
            "Zestaw danych syntetycznych przeznaczony do testowania "
            "generatora okazji i algorytmów harmonogramowania."
        ),
    )


def main() -> None:
    request_set = build_request_set()

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_data = request_set.model_dump(
        mode="json",
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            output_data,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Zapisano {len(request_set.requests)} zleceń do:"
    )
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()