from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.version import __version__


PROJECT_ARCHIVE_SCHEMA_VERSION = "1.0.0"
APPLICATION_VERSION = __version__


class ProjectMetadata(BaseModel):
    """Metadane przenośnego archiwum projektu SatPlan."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: str = Field(pattern=r"^PROJECT-[A-Z0-9-]+$")
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=2000)
    author: str = Field(default="", max_length=150)
    schema_version: str = PROJECT_ARCHIVE_SCHEMA_VERSION
    application_version: str = APPLICATION_VERSION
    created_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    exported_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    source: str = "Satellite Acquisition Planner"
    component_counts: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @field_validator("created_at_utc", "exported_at_utc")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Czas metadanych musi zawierać strefę czasową")
        return value.astimezone(timezone.utc)


class ProjectManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    required: bool = False


class ProjectManifest(BaseModel):
    """Manifest integralności archiwum projektu."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = PROJECT_ARCHIVE_SCHEMA_VERSION
    generated_at_utc: datetime
    files: list[ProjectManifestEntry]

    @field_validator("generated_at_utc")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at_utc musi zawierać strefę czasową")
        return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ProjectArchivePreview:
    """Zwalidowany podgląd archiwum przed zmianą stanu sesji."""

    metadata: ProjectMetadata
    restored_state: dict[str, Any]
    present_components: tuple[str, ...]
    warnings: tuple[str, ...]
    file_count: int
    uncompressed_size_bytes: int

    @property
    def request_count(self) -> int:
        return len(self.restored_state.get("custom_observation_requests", ()))

    @property
    def opportunity_count(self) -> int:
        builds = self.restored_state.get("public_opportunity_builds", {})
        build_count = sum(
            len(build.opportunities) for build in builds.values()
        )
        if build_count:
            return build_count
        planning = self.restored_state.get("public_planning_result")
        scenario = getattr(planning, "scenario", None)
        return int(getattr(scenario, "opportunity_count", 0))

    @property
    def schedule_count(self) -> int:
        history = self.restored_state.get("project_schedule_history", ())
        return len(history)


@dataclass(frozen=True, slots=True)
class ProjectExportResult:
    archive_bytes: bytes
    metadata: ProjectMetadata
    included_files: tuple[str, ...]
    warnings: tuple[str, ...]


__all__ = [
    "APPLICATION_VERSION",
    "PROJECT_ARCHIVE_SCHEMA_VERSION",
    "ProjectArchivePreview",
    "ProjectExportResult",
    "ProjectManifest",
    "ProjectManifestEntry",
    "ProjectMetadata",
]
