from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.integrations.opportunities import PublicOpportunityBuildResult
from app.integrations.orbits import (
    CelestrakQueryResult,
    PublicOrbitRecord,
    SatelliteFamily,
    TrackedSatellite,
)
from app.models.enums import PlanningAlgorithm
from app.projects import ProjectArchiveService, record_schedule_history
from app.projects.codec import decode_orbit_snapshot, encode_orbit_snapshot
from app.projects.service import (
    AOI_STATE_KEY,
    CUSTOM_REQUESTS_STATE_KEY,
    OPPORTUNITY_BUILDS_STATE_KEY,
    ORBIT_SNAPSHOT_STATE_KEY,
    PLANNING_RESULT_STATE_KEY,
)
from app.services.contracts import PlanningOptions, PlanningResult
from app.services.orbit_service import PublicConstellationSnapshot
from app.services.planning_service import PlanningService
from app.services.scenario_service import ScenarioService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _omm(name: str = "ICEYE-X1", norad: int = 65001) -> dict[str, object]:
    return {
        "OBJECT_NAME": name,
        "OBJECT_ID": "2024-001A",
        "EPOCH": "2026-07-17T00:00:00.000000",
        "MEAN_MOTION": 15.2,
        "ECCENTRICITY": 0.0003,
        "INCLINATION": 97.8,
        "RA_OF_ASC_NODE": 120.0,
        "ARG_OF_PERICENTER": 10.0,
        "MEAN_ANOMALY": 20.0,
        "BSTAR": 0.00001,
        "MEAN_MOTION_DOT": 0.0,
        "MEAN_MOTION_DDOT": 0.0,
        "ELEMENT_SET_NO": 1,
        "REV_AT_EPOCH": 100,
        "NORAD_CAT_ID": norad,
        "CLASSIFICATION_TYPE": "U",
        "EPHEMERIS_TYPE": 0,
    }


def _snapshot() -> PublicConstellationSnapshot:
    record = PublicOrbitRecord.from_omm(_omm())
    tracked = TrackedSatellite(
        slot_id="SAR-01",
        family=SatelliteFamily.ICEYE,
        record=record,
    )
    query = CelestrakQueryResult(
        query_name="ICEYE",
        records=(record,),
        fetched_at_utc=datetime(2026, 7, 17, tzinfo=timezone.utc),
        request_url="https://example.invalid/omm",
        from_cache=True,
        is_stale=False,
    )
    return PublicConstellationSnapshot(
        generated_at_utc=datetime(2026, 7, 17, tzinfo=timezone.utc),
        satellites=(tracked,),
        queries=(query,),
        warnings=(),
    )


def _planning_result() -> PlanningResult:
    scenario = ScenarioService(project_root=PROJECT_ROOT).load("EXAMPLE")
    return PlanningService().run(
        scenario=scenario,
        options=PlanningOptions(algorithm=PlanningAlgorithm.GREEDY),
        schedule_id="SCHEDULE-PROJECT-ROUNDTRIP",
        schedule_name="Project archive roundtrip",
    )


def test_orbit_snapshot_codec_preserves_raw_omm() -> None:
    original = _snapshot()
    restored = decode_orbit_snapshot(encode_orbit_snapshot(original))

    assert restored.satellites[0].slot_id == "SAR-01"
    assert restored.satellites[0].record.norad_cat_id == 65001
    assert restored.satellites[0].record.raw_omm["OBJECT_NAME"] == "ICEYE-X1"
    assert restored.queries[0].from_cache is True


def test_project_archive_roundtrip_restores_core_session_state() -> None:
    planning = _planning_result()
    first_request = planning.scenario.request_set.requests[0]
    first_opportunity = next(
        opportunity
        for opportunity in planning.scenario.opportunity_set.opportunities
        if opportunity.request_id == first_request.request_id
    )
    build = PublicOpportunityBuildResult(
        request_id=first_request.request_id,
        generated_at_utc=datetime.now(timezone.utc),
        opportunities=(first_opportunity,),
        weather_assessments=(),
        skipped_window_ids=(),
        warnings=(),
    )
    state: dict[str, object] = {
        AOI_STATE_KEY: first_request.geometry,
        CUSTOM_REQUESTS_STATE_KEY: list(
            planning.scenario.request_set.requests
        ),
        ORBIT_SNAPSHOT_STATE_KEY: _snapshot(),
        OPPORTUNITY_BUILDS_STATE_KEY: {
            first_request.request_id: build,
        },
        PLANNING_RESULT_STATE_KEY: planning,
    }
    record_schedule_history(
        state,
        planning,
        event_type="INITIAL_PLANNING",
    )

    service = ProjectArchiveService()
    exported = service.export_project(
        state,
        project_name="Test projektu",
        author="pytest",
        description="Roundtrip pełnego stanu",
    )
    preview = service.preview_archive(exported.archive_bytes)

    assert preview.metadata.name == "Test projektu"
    assert preview.request_count == len(planning.scenario.request_set.requests)
    assert preview.opportunity_count == 1
    assert "Harmonogram" in preview.present_components
    assert "Snapshot orbit" in preview.present_components

    restored: dict[str, object] = {"unrelated_widget": "keep"}
    service.apply_preview(restored, preview)

    assert restored["unrelated_widget"] == "keep"
    assert len(restored[CUSTOM_REQUESTS_STATE_KEY]) == preview.request_count
    restored_planning = restored[PLANNING_RESULT_STATE_KEY]
    assert isinstance(restored_planning, PlanningResult)
    assert restored_planning.schedule.schedule_id == planning.schedule.schedule_id
    assert restored_planning.analysis.schedule_id == planning.schedule.schedule_id
    restored_snapshot = restored[ORBIT_SNAPSHOT_STATE_KEY]
    assert isinstance(restored_snapshot, PublicConstellationSnapshot)


def test_project_archive_rejects_checksum_mismatch() -> None:
    service = ProjectArchiveService()
    exported = service.export_project(
        {CUSTOM_REQUESTS_STATE_KEY: []},
        project_name="Checksum",
    )
    input_zip = zipfile.ZipFile(io.BytesIO(exported.archive_bytes))
    files = {name: input_zip.read(name) for name in input_zip.namelist()}
    input_zip.close()
    files["metadata.json"] = files["metadata.json"] + b" "

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)

    with pytest.raises(ValueError, match="SHA-256|rozmiar"):
        service.preview_archive(buffer.getvalue())


def test_project_archive_rejects_path_traversal() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../metadata.json", b"{}")

    with pytest.raises(ValueError, match="Niebezpieczna ścieżka"):
        ProjectArchiveService().preview_archive(buffer.getvalue())
