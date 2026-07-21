from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping

from app.analysis.algorithm_benchmark import AlgorithmBenchmarkResult
from app.integrations.access import AccessCalculationResult
from app.integrations.opportunities import PublicOpportunityBuildResult
from app.models.request import ObservationRequest
from app.models.schedule import Schedule
from app.services.contracts import PlanningResult, PublicReplanningResult
from app.services.orbit_service import PublicConstellationSnapshot
from app.projects.codec import (
    decode_access_result,
    decode_aoi,
    decode_benchmark_result,
    decode_opportunity_builds,
    decode_orbit_snapshot,
    decode_planning_options,
    decode_planning_result,
    decode_public_replanning_result,
    decode_requests,
    encode_access_result,
    encode_aoi,
    encode_benchmark_result,
    encode_opportunity_builds,
    encode_orbit_snapshot,
    encode_planning_result,
    encode_public_replanning_result,
    encode_requests,
    jsonable,
)
from app.projects.history import (
    PROJECT_METADATA_STATE_KEY,
    SCHEDULE_HISTORY_STATE_KEY,
    build_schedule_history_entry,
)
from app.projects.models import (
    APPLICATION_VERSION,
    PROJECT_ARCHIVE_SCHEMA_VERSION,
    ProjectArchivePreview,
    ProjectExportResult,
    ProjectManifest,
    ProjectManifestEntry,
    ProjectMetadata,
)


CUSTOM_REQUESTS_STATE_KEY = "custom_observation_requests"
AOI_STATE_KEY = "target_definition_geometry"
ORBIT_SNAPSHOT_STATE_KEY = "public_orbit_snapshot"
ACCESS_RESULT_STATE_KEY = "public_access_result"
OPPORTUNITY_BUILDS_STATE_KEY = "public_opportunity_builds"
PLANNING_RESULT_STATE_KEY = "public_planning_result"
REPLANNING_RESULT_STATE_KEY = "public_replanning_result"
BENCHMARK_RESULT_STATE_KEY = "algorithm_benchmark_result"

PROJECT_SESSION_STATE_KEYS = (
    AOI_STATE_KEY,
    CUSTOM_REQUESTS_STATE_KEY,
    ORBIT_SNAPSHOT_STATE_KEY,
    ACCESS_RESULT_STATE_KEY,
    OPPORTUNITY_BUILDS_STATE_KEY,
    PLANNING_RESULT_STATE_KEY,
    REPLANNING_RESULT_STATE_KEY,
    BENCHMARK_RESULT_STATE_KEY,
    SCHEDULE_HISTORY_STATE_KEY,
    PROJECT_METADATA_STATE_KEY,
)

_MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
_MAX_FILE_COUNT = 100
_REQUIRED_FILES = {"metadata.json", "manifest.json"}


def _dump_json(payload: Any) -> bytes:
    return json.dumps(
        jsonable(payload),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")


def _load_json(raw: bytes, *, path: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Niepoprawny JSON w pliku {path}: {error}") from error


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _normalize_project_id(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "-", value.strip().upper()).strip("-")
    if not normalized:
        normalized = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"PROJECT-{normalized[:80]}"


def _archive_filename(name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-._")
    return f"{normalized or 'projekt-satplan'}.satplan.zip"


def _component_counts(state: Mapping[str, Any]) -> dict[str, int]:
    requests = state.get(CUSTOM_REQUESTS_STATE_KEY, ())
    builds = state.get(OPPORTUNITY_BUILDS_STATE_KEY, {})
    planning = state.get(PLANNING_RESULT_STATE_KEY)
    history = state.get(SCHEDULE_HISTORY_STATE_KEY, ())
    build_opportunity_count = sum(
        len(build.opportunities) for build in builds.values()
    )
    planning_opportunity_count = (
        planning.scenario.opportunity_count
        if isinstance(planning, PlanningResult)
        else 0
    )
    return {
        "requests": len(requests),
        "opportunity_builds": len(builds),
        "opportunities": (
            build_opportunity_count
            if build_opportunity_count
            else planning_opportunity_count
        ),
        "access_windows": len(
            getattr(state.get(ACCESS_RESULT_STATE_KEY), "windows", ())
        ),
        "schedule_entries": len(
            planning.schedule.active_entries
            if isinstance(planning, PlanningResult)
            else ()
        ),
        "schedule_versions": len(history),
    }


def _current_schedule_history(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    history = [dict(item) for item in state.get(SCHEDULE_HISTORY_STATE_KEY, ())]
    planning = state.get(PLANNING_RESULT_STATE_KEY)
    if isinstance(planning, PlanningResult):
        signature = (
            f"{planning.schedule.schedule_id}:"
            f"{planning.schedule.created_at_utc.isoformat()}"
        )
        if not any(item.get("schedule_signature") == signature for item in history):
            history.append(
                build_schedule_history_entry(
                    planning,
                    event_type="CURRENT_EXPORT",
                )
            )
    return history


class ProjectArchiveService:
    """Eksportuje, waliduje i transakcyjnie odtwarza projekty sesyjne."""

    def export_project(
        self,
        state: Mapping[str, Any],
        *,
        project_name: str,
        description: str = "",
        author: str = "",
    ) -> ProjectExportResult:
        now = datetime.now(timezone.utc)
        previous_metadata = state.get(PROJECT_METADATA_STATE_KEY)
        created_at = (
            previous_metadata.created_at_utc
            if isinstance(previous_metadata, ProjectMetadata)
            else now
        )
        metadata = ProjectMetadata(
            project_id=_normalize_project_id(project_name),
            name=project_name,
            description=description,
            author=author,
            created_at_utc=created_at,
            exported_at_utc=now,
            component_counts=_component_counts(state),
            notes=[
                "Dane orbit i pogody są snapshotem użytym w obliczeniach.",
                "Publiczne profile sensorów nie potwierdzają dostępności taskingu operatora.",
            ],
        )
        files: dict[str, bytes] = {
            "metadata.json": _dump_json(metadata),
        }
        warnings: list[str] = []

        geometry = state.get(AOI_STATE_KEY)
        if geometry is not None:
            files["aoi.geojson"] = _dump_json(encode_aoi(geometry))

        requests = state.get(CUSTOM_REQUESTS_STATE_KEY, ())
        if requests:
            if not all(isinstance(item, ObservationRequest) for item in requests):
                raise TypeError("Stan zleceń zawiera nieobsługiwane obiekty")
            files["requests.json"] = _dump_json(encode_requests(list(requests)))

        snapshot = state.get(ORBIT_SNAPSHOT_STATE_KEY)
        if snapshot is not None:
            if not isinstance(snapshot, PublicConstellationSnapshot):
                raise TypeError("Stan orbit zawiera nieobsługiwany obiekt")
            files["orbit_snapshot.json"] = _dump_json(
                encode_orbit_snapshot(snapshot)
            )

        access = state.get(ACCESS_RESULT_STATE_KEY)
        if access is not None:
            if not isinstance(access, AccessCalculationResult):
                raise TypeError("Stan okien dostępu zawiera nieobsługiwany obiekt")
            files["access_windows.json"] = _dump_json(
                encode_access_result(access)
            )

        builds = state.get(OPPORTUNITY_BUILDS_STATE_KEY, {})
        if builds:
            if not all(
                isinstance(item, PublicOpportunityBuildResult)
                for item in builds.values()
            ):
                raise TypeError("Stan okazji publicznych jest niepoprawny")
            encoded_builds = encode_opportunity_builds(builds)
            files["opportunity_builds.json"] = _dump_json(encoded_builds)
            files["weather_assessments.json"] = _dump_json(
                {
                    request_id: [
                        assessment.to_dict()
                        for assessment in build.weather_assessments
                    ]
                    for request_id, build in sorted(builds.items())
                }
            )
            files["opportunities.json"] = _dump_json(
                [
                    opportunity.model_dump(mode="json")
                    for request_id in sorted(builds)
                    for opportunity in builds[request_id].opportunities
                ]
            )

        planning = state.get(PLANNING_RESULT_STATE_KEY)
        if planning is not None:
            if not isinstance(planning, PlanningResult):
                raise TypeError("Stan planowania zawiera nieobsługiwany obiekt")
            files["planning_result.json"] = _dump_json(
                encode_planning_result(planning)
            )
            files["scenario.json"] = _dump_json(
                encode_planning_result(planning)["scenario"]
            )
            files["schedule.json"] = _dump_json(
                planning.schedule.model_dump(mode="json")
            )

        history = _current_schedule_history(state)
        if history:
            files["schedule_history.json"] = _dump_json(history)

        replanning = state.get(REPLANNING_RESULT_STATE_KEY)
        if replanning is not None:
            if not isinstance(replanning, PublicReplanningResult):
                raise TypeError("Stan przeplanowania zawiera nieobsługiwany obiekt")
            encoded_replanning = encode_public_replanning_result(replanning)
            files["public_replanning_result.json"] = _dump_json(
                encoded_replanning
            )
            files["replanning_history.json"] = _dump_json(
                [
                    {
                        "refreshed_at_utc": encoded_replanning[
                            "refreshed_at_utc"
                        ],
                        "replan_at_utc": encoded_replanning["replan_at_utc"],
                        "frozen_until_utc": encoded_replanning[
                            "frozen_until_utc"
                        ],
                        "weather_changes": encoded_replanning[
                            "weather_changes"
                        ],
                        "warnings": encoded_replanning["warnings"],
                    }
                ]
            )

        benchmark = state.get(BENCHMARK_RESULT_STATE_KEY)
        if benchmark is not None:
            if not isinstance(benchmark, AlgorithmBenchmarkResult):
                raise TypeError("Stan benchmarku zawiera nieobsługiwany obiekt")
            encoded_benchmark = encode_benchmark_result(benchmark)
            files["benchmark_config.json"] = _dump_json(
                encoded_benchmark["config"]
            )
            files["benchmark_results.json"] = _dump_json(encoded_benchmark)

        files["README.txt"] = (
            "Satellite Acquisition Planner — archiwum projektu\n"
            f"Schemat: {PROJECT_ARCHIVE_SCHEMA_VERSION}\n"
            f"Aplikacja: {APPLICATION_VERSION}\n\n"
            "Archiwum należy importować w module „Projekty i scenariusze”.\n"
            "manifest.json zawiera sumy SHA-256 wszystkich plików danych.\n"
        ).encode("utf-8")

        manifest_entries = [
            ProjectManifestEntry(
                path=path,
                size_bytes=len(raw),
                sha256=_sha256(raw),
                required=path == "metadata.json",
            )
            for path, raw in sorted(files.items())
        ]
        manifest = ProjectManifest(
            generated_at_utc=now,
            files=manifest_entries,
        )
        files["manifest.json"] = _dump_json(manifest)

        buffer = io.BytesIO()
        with zipfile.ZipFile(
            buffer,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for path, raw in sorted(files.items()):
                archive.writestr(path, raw)

        if not requests:
            warnings.append("Projekt nie zawiera zleceń obserwacyjnych.")
        if planning is None:
            warnings.append("Projekt nie zawiera harmonogramu.")
        return ProjectExportResult(
            archive_bytes=buffer.getvalue(),
            metadata=metadata,
            included_files=tuple(sorted(files)),
            warnings=tuple(warnings),
        )

    def preview_archive(self, archive_bytes: bytes) -> ProjectArchivePreview:
        if not archive_bytes:
            raise ValueError("Archiwum jest puste")
        if len(archive_bytes) > _MAX_ARCHIVE_BYTES:
            raise ValueError("Archiwum przekracza limit 50 MB")

        files = self._read_zip(archive_bytes)
        missing = _REQUIRED_FILES - files.keys()
        if missing:
            raise ValueError(
                "Brak wymaganych plików: " + ", ".join(sorted(missing))
            )

        manifest = ProjectManifest.model_validate(
            _load_json(files["manifest.json"], path="manifest.json")
        )
        if manifest.schema_version != PROJECT_ARCHIVE_SCHEMA_VERSION:
            raise ValueError(
                "Nieobsługiwana wersja schematu projektu: "
                f"{manifest.schema_version}"
            )
        self._verify_manifest(files, manifest)

        metadata = ProjectMetadata.model_validate(
            _load_json(files["metadata.json"], path="metadata.json")
        )
        if metadata.schema_version != PROJECT_ARCHIVE_SCHEMA_VERSION:
            raise ValueError(
                "Metadane mają nieobsługiwaną wersję schematu: "
                f"{metadata.schema_version}"
            )

        restored: dict[str, Any] = {
            PROJECT_METADATA_STATE_KEY: metadata,
        }
        present: list[str] = []
        warnings: list[str] = []

        if "aoi.geojson" in files:
            restored[AOI_STATE_KEY] = decode_aoi(
                _load_json(files["aoi.geojson"], path="aoi.geojson")
            )
            present.append("AOI")

        if "requests.json" in files:
            restored[CUSTOM_REQUESTS_STATE_KEY] = decode_requests(
                _load_json(files["requests.json"], path="requests.json")
            )
            present.append("Zlecenia")
        else:
            restored[CUSTOM_REQUESTS_STATE_KEY] = []

        if "orbit_snapshot.json" in files:
            restored[ORBIT_SNAPSHOT_STATE_KEY] = decode_orbit_snapshot(
                _load_json(
                    files["orbit_snapshot.json"],
                    path="orbit_snapshot.json",
                )
            )
            present.append("Snapshot orbit")

        if "access_windows.json" in files:
            restored[ACCESS_RESULT_STATE_KEY] = decode_access_result(
                _load_json(
                    files["access_windows.json"],
                    path="access_windows.json",
                )
            )
            present.append("Okna dostępu")

        if "opportunity_builds.json" in files:
            restored[OPPORTUNITY_BUILDS_STATE_KEY] = decode_opportunity_builds(
                _load_json(
                    files["opportunity_builds.json"],
                    path="opportunity_builds.json",
                )
            )
            present.append("Okazje i pogoda")
        else:
            restored[OPPORTUNITY_BUILDS_STATE_KEY] = {}

        if "planning_result.json" in files:
            restored[PLANNING_RESULT_STATE_KEY] = decode_planning_result(
                _load_json(
                    files["planning_result.json"],
                    path="planning_result.json",
                )
            )
            present.append("Harmonogram")

        if "schedule_history.json" in files:
            history = _load_json(
                files["schedule_history.json"],
                path="schedule_history.json",
            )
            if not isinstance(history, list):
                raise ValueError("schedule_history.json musi zawierać listę")
            for index, item in enumerate(history, start=1):
                if not isinstance(item, Mapping):
                    raise ValueError(
                        f"Wpis historii {index} nie jest obiektem JSON"
                    )
                schedule_payload = item.get("schedule")
                if not isinstance(schedule_payload, Mapping):
                    raise ValueError(
                        f"Wpis historii {index} nie zawiera harmonogramu"
                    )
                Schedule.model_validate(schedule_payload)
                options_payload = item.get("options")
                if options_payload is not None:
                    if not isinstance(options_payload, Mapping):
                        raise ValueError(
                            f"Opcje historii {index} nie są obiektem JSON"
                        )
                    decode_planning_options(options_payload)
            restored[SCHEDULE_HISTORY_STATE_KEY] = history
            present.append("Historia harmonogramów")
        else:
            restored[SCHEDULE_HISTORY_STATE_KEY] = []

        if "public_replanning_result.json" in files:
            replanning = decode_public_replanning_result(
                _load_json(
                    files["public_replanning_result.json"],
                    path="public_replanning_result.json",
                )
            )
            restored[REPLANNING_RESULT_STATE_KEY] = replanning
            restored[PLANNING_RESULT_STATE_KEY] = replanning.planning_result
            restored[OPPORTUNITY_BUILDS_STATE_KEY] = (
                replanning.refreshed_builds_by_request_id
            )
            present.append("Przeplanowanie publiczne")

        if "benchmark_results.json" in files:
            restored[BENCHMARK_RESULT_STATE_KEY] = decode_benchmark_result(
                _load_json(
                    files["benchmark_results.json"],
                    path="benchmark_results.json",
                )
            )
            present.append("Benchmark")

        self._validate_restored_state(restored)
        planning = restored.get(PLANNING_RESULT_STATE_KEY)
        project_requests = restored.get(CUSTOM_REQUESTS_STATE_KEY, ())
        if isinstance(planning, PlanningResult) and project_requests:
            planned_request_count = len(
                planning.scenario.request_set.requests
            )
            if planned_request_count != len(project_requests):
                warnings.append(
                    "Zapisany harmonogram obejmuje "
                    f"{planned_request_count} z {len(project_requests)} "
                    "zleceń projektu. Pozostałe zlecenia są zachowane, "
                    "ale nie należą do aktywnego wyniku planowania."
                )
        if metadata.application_version != APPLICATION_VERSION:
            warnings.append(
                "Projekt utworzono w wersji aplikacji "
                f"{metadata.application_version}; bieżąca wersja to "
                f"{APPLICATION_VERSION}."
            )
        return ProjectArchivePreview(
            metadata=metadata,
            restored_state=restored,
            present_components=tuple(present),
            warnings=tuple(warnings),
            file_count=len(files),
            uncompressed_size_bytes=sum(len(raw) for raw in files.values()),
        )

    def apply_preview(
        self,
        state: MutableMapping[str, Any],
        preview: ProjectArchivePreview,
    ) -> None:
        """Podmienia stan dopiero po pełnej walidacji archiwum."""

        for key in PROJECT_SESSION_STATE_KEYS:
            state.pop(key, None)
        for key, value in preview.restored_state.items():
            state[key] = value

    def clear_project(self, state: MutableMapping[str, Any]) -> None:
        for key in PROJECT_SESSION_STATE_KEYS:
            state.pop(key, None)

    @staticmethod
    def suggested_filename(project_name: str) -> str:
        return _archive_filename(project_name)

    @staticmethod
    def _read_zip(archive_bytes: bytes) -> dict[str, bytes]:
        try:
            archive = zipfile.ZipFile(io.BytesIO(archive_bytes), mode="r")
        except zipfile.BadZipFile as error:
            raise ValueError("Plik nie jest poprawnym archiwum ZIP") from error
        with archive:
            infos = archive.infolist()
            if len(infos) > _MAX_FILE_COUNT:
                raise ValueError("Archiwum zawiera zbyt wiele plików")
            total = sum(info.file_size for info in infos)
            if total > _MAX_UNCOMPRESSED_BYTES:
                raise ValueError("Rozpakowane dane przekraczają limit 250 MB")
            files: dict[str, bytes] = {}
            for info in infos:
                path = info.filename.replace("\\", "/")
                if (
                    path.startswith("/")
                    or path.startswith("../")
                    or "/../" in path
                    or re.match(r"^[A-Za-z]:", path)
                ):
                    raise ValueError(f"Niebezpieczna ścieżka w ZIP: {path}")
                if info.is_dir():
                    continue
                if path in files:
                    raise ValueError(f"Powtórzony plik w archiwum: {path}")
                files[path] = archive.read(info)
            return files

    @staticmethod
    def _verify_manifest(
        files: Mapping[str, bytes],
        manifest: ProjectManifest,
    ) -> None:
        declared = {entry.path: entry for entry in manifest.files}
        if len(declared) != len(manifest.files):
            raise ValueError("Manifest zawiera powtórzone ścieżki")
        for path, entry in declared.items():
            raw = files.get(path)
            if raw is None:
                raise ValueError(f"Brak pliku zadeklarowanego w manifeście: {path}")
            if len(raw) != entry.size_bytes:
                raise ValueError(f"Niezgodny rozmiar pliku: {path}")
            if _sha256(raw) != entry.sha256:
                raise ValueError(f"Niezgodna suma SHA-256 pliku: {path}")
        undeclared = set(files) - set(declared) - {"manifest.json"}
        if undeclared:
            raise ValueError(
                "Archiwum zawiera pliki spoza manifestu: "
                + ", ".join(sorted(undeclared))
            )

    @staticmethod
    def _validate_restored_state(state: Mapping[str, Any]) -> None:
        requests = state.get(CUSTOM_REQUESTS_STATE_KEY, ())
        request_ids = {request.request_id for request in requests}
        builds = state.get(OPPORTUNITY_BUILDS_STATE_KEY, {})
        unknown_builds = set(builds) - request_ids
        if unknown_builds:
            raise ValueError(
                "Okazje odwołują się do nieznanych zleceń: "
                + ", ".join(sorted(unknown_builds))
            )
        for request_id, build in builds.items():
            if any(
                opportunity.request_id != request_id
                for opportunity in build.opportunities
            ):
                raise ValueError(
                    f"Okazje dla {request_id} mają niespójne request_id"
                )
        access = state.get(ACCESS_RESULT_STATE_KEY)
        if access is not None and access.request_id not in request_ids:
            raise ValueError(
                "Wynik okien dostępu odwołuje się do nieznanego zlecenia"
            )
        planning = state.get(PLANNING_RESULT_STATE_KEY)
        if planning is not None:
            scenario_request_ids = {
                request.request_id
                for request in planning.scenario.request_set.requests
            }
            if request_ids and not scenario_request_ids.issubset(request_ids):
                raise ValueError(
                    "Harmonogram zawiera zlecenia nieobecne w projekcie"
                )


__all__ = [
    "ACCESS_RESULT_STATE_KEY",
    "AOI_STATE_KEY",
    "BENCHMARK_RESULT_STATE_KEY",
    "CUSTOM_REQUESTS_STATE_KEY",
    "OPPORTUNITY_BUILDS_STATE_KEY",
    "ORBIT_SNAPSHOT_STATE_KEY",
    "PLANNING_RESULT_STATE_KEY",
    "PROJECT_SESSION_STATE_KEYS",
    "ProjectArchiveService",
    "REPLANNING_RESULT_STATE_KEY",
]
