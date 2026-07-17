from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone

from app.geospatial.aoi import geometry_centroid, target_geometry_to_feature
from app.integrations.access.models import GeometricAccessWindow
from app.integrations.orbits import TrackedSatellite
from app.models.imaging import ImagingMode
from app.models.request import ObservationRequest


def _windows_csv(windows: tuple[GeometricAccessWindow, ...]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "window_id",
            "start_utc",
            "end_utc",
            "duration_s",
            "peak_utc",
            "observation_side",
            "min_off_nadir_deg",
            "max_off_nadir_deg",
            "min_incidence_deg",
            "max_incidence_deg",
        ],
    )
    writer.writeheader()
    for window in windows:
        writer.writerow(
            {
                "window_id": window.window_id,
                "start_utc": window.start_utc.isoformat(),
                "end_utc": window.end_utc.isoformat(),
                "duration_s": f"{window.duration_s:.6f}",
                "peak_utc": window.peak_utc.isoformat(),
                "observation_side": window.observation_side.value,
                "min_off_nadir_deg": f"{window.minimum_off_nadir_deg:.6f}",
                "max_off_nadir_deg": f"{window.maximum_off_nadir_deg:.6f}",
                "min_incidence_deg": (
                    f"{window.minimum_incidence_angle_deg:.6f}"
                ),
                "max_incidence_deg": (
                    f"{window.maximum_incidence_angle_deg:.6f}"
                ),
            }
        )
    return output.getvalue()


def _target_vertices_csv(request: ObservationRequest) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ring", "vertex", "longitude_deg", "latitude_deg"])
    geometry = request.geometry
    if geometry.type == "Point":
        longitude, latitude = geometry.coordinates
        writer.writerow([0, 0, longitude, latitude])
    else:
        for ring_index, ring in enumerate(geometry.coordinates):
            for vertex_index, (longitude, latitude) in enumerate(ring):
                writer.writerow(
                    [ring_index, vertex_index, longitude, latitude]
                )
    return output.getvalue()


def build_stk_validation_bundle(
    *,
    request: ObservationRequest,
    satellite: TrackedSatellite,
    mode: ImagingMode,
    windows: tuple[GeometricAccessWindow, ...],
    propagation_step_s: float,
) -> bytes:
    """Buduje ZIP z kompletem danych potrzebnych do odtworzenia przypadku w STK."""

    longitude, latitude = geometry_centroid(request.geometry)
    manifest = {
        "schema": "satplan.stk_validation_case.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "request": request.model_dump(mode="json"),
        "satellite": satellite.to_dict(),
        "mode": mode.model_dump(mode="json"),
        "model": {
            "propagator": "SGP4",
            "orbit_source": "CELESTRAK_OMM",
            "propagation_step_s": propagation_step_s,
            "window_count": len(windows),
        },
        "stk_setup": {
            "scenario_start_utc": request.earliest_start_utc.isoformat(),
            "scenario_end_utc": request.latest_end_utc.isoformat(),
            "target_centroid_longitude_deg": longitude,
            "target_centroid_latitude_deg": latitude,
            "recommended_time_system": "UTCG",
            "recommended_access_report_columns": [
                "Access Number",
                "Start Time (UTCG)",
                "Stop Time (UTCG)",
                "Duration (sec)",
            ],
            "recommended_aer_report_columns": [
                "Time (UTCG)",
                "Azimuth (deg)",
                "Elevation (deg)",
                "Range (km)",
            ],
        },
    }
    instructions = f"""WALIDACJA SATPLAN W STK

1. Utwórz scenariusz STK w przedziale:
   {request.earliest_start_utc.isoformat()} – {request.latest_end_utc.isoformat()}
   i ustaw jednostkę czasu UTCG.

2. Dodaj satelitę na podstawie satellite_omm.json.
   Slot planera: {satellite.slot_id}
   Obiekt publiczny: {satellite.record.object_name}
   NORAD CAT ID: {satellite.record.norad_cat_id}
   Epoka OMM: {satellite.record.epoch_utc.isoformat()}
   Propagator porównawczy: SGP4.

3. Dodaj cel:
   - Point: użyj target_centroid.json albo target.geojson;
   - Polygon: utwórz Area Target z target_vertices.csv.
   Centroid kontrolny: longitude={longitude:.8f}, latitude={latitude:.8f}.

4. Skonfiguruj sensor zgodnie z mode.json. Przypadek walidacyjny:
   tryb={mode.name}, sensor={mode.sensor_type.value},
   max off-nadir={mode.max_off_nadir_deg:g} deg.

5. Oblicz Access między sensorem/satelitą i celem. Wyeksportuj CSV z kolumnami:
   Access Number, Start Time (UTCG), Stop Time (UTCG), Duration (sec).

6. Opcjonalnie wyeksportuj raport AER z kolumnami:
   Time (UTCG), Azimuth (deg), Elevation (deg), Range (km).

7. Zaimportuj oba raporty w module „Walidacja STK” aplikacji.

UWAGA: dla Polygon model SatPlan szacuje pokrycie nominalnym footprintem. Walidacja
czasów dostępu i AER dotyczy geometrii centroidu/Area Target, a nie komercyjnej
gwarancji taskingu operatora.
"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
        archive.writestr(
            "satellite_omm.json",
            json.dumps(
                satellite.record.to_omm_fields(),
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr(
            "mode.json",
            json.dumps(mode.model_dump(mode="json"), ensure_ascii=False, indent=2),
        )
        archive.writestr(
            "target.geojson",
            json.dumps(
                target_geometry_to_feature(request.geometry),
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr(
            "target_centroid.json",
            json.dumps(
                {
                    "longitude_deg": longitude,
                    "latitude_deg": latitude,
                    "altitude_km": 0.0,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr("target_vertices.csv", _target_vertices_csv(request))
        archive.writestr("model_access_windows.csv", _windows_csv(windows))
        archive.writestr("STK_VALIDATION_INSTRUCTIONS.txt", instructions)
    return buffer.getvalue()
