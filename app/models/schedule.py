import re
from datetime import datetime, timezone
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import (
    PlanningAlgorithm,
    ScheduleEntryStatus,
    ScheduleStatus,
    SensorType,
)


class ScheduleEntry(BaseModel):
    """Pojedyncza akwizycja umieszczona w harmonogramie."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    entry_id: str = Field(
        pattern=r"^ENTRY-[A-Z0-9-]+$",
        description="Unikalny identyfikator wpisu harmonogramu.",
    )

    opportunity_id: str = Field(
        pattern=r"^OPP-[A-Z0-9-]+$",
    )

    request_id: str = Field(
        pattern=r"^REQ-[A-Z0-9-]+$",
    )

    satellite_id: str = Field(
        pattern=r"^(SAR|EO)-[0-9]{2}$",
    )

    sensor_id: str = Field(
        pattern=r"^SENSOR-[A-Z0-9-]+$",
    )

    mode_id: str = Field(
        pattern=r"^MODE-[A-Z0-9-]+$",
    )

    sensor_type: SensorType

    start_utc: datetime
    end_utc: datetime

    status: ScheduleEntryStatus = ScheduleEntryStatus.PLANNED

    estimated_data_volume_mb: float = Field(
        gt=0.0,
    )

    objective_contribution: float = Field(
        ge=0.0,
    )

    lock_reason: str | None = Field(
        default=None,
        max_length=500,
    )

    notes: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator(
        "start_utc",
        "end_utc",
    )
    @classmethod
    def validate_utc_datetime(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Czas wpisu harmonogramu musi zawierać strefę czasową"
            )

        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_entry_configuration(
        self,
    ) -> "ScheduleEntry":
        self._validate_time_window()
        self._validate_platform_assignment()
        self._validate_lock_configuration()

        return self

    def _validate_time_window(self) -> None:
        if self.start_utc >= self.end_utc:
            raise ValueError(
                "start_utc musi być wcześniejsze niż end_utc"
            )

    def _validate_platform_assignment(self) -> None:
        if self.sensor_type == SensorType.SAR:
            expected_satellite_prefix = "SAR-"
            expected_sensor_prefix = "SENSOR-SAR-"
            expected_mode_prefix = "MODE-SAR-"
        else:
            expected_satellite_prefix = "EO-"
            expected_sensor_prefix = "SENSOR-EO-"
            expected_mode_prefix = "MODE-OPT-"

        if not self.satellite_id.startswith(
            expected_satellite_prefix
        ):
            raise ValueError(
                "sensor_type jest niezgodny z satellite_id"
            )

        if not self.sensor_id.startswith(
            expected_sensor_prefix
        ):
            raise ValueError(
                "sensor_type jest niezgodny z sensor_id"
            )

        if not self.mode_id.startswith(
            expected_mode_prefix
        ):
            raise ValueError(
                "sensor_type jest niezgodny z mode_id"
            )

    def _validate_lock_configuration(self) -> None:
        if self.status == ScheduleEntryStatus.FROZEN:
            if not self.lock_reason:
                raise ValueError(
                    "Wpis FROZEN musi posiadać lock_reason"
                )

        elif self.lock_reason is not None:
            raise ValueError(
                "lock_reason może być ustawione tylko dla wpisu FROZEN"
            )

    @property
    def duration_s(self) -> float:
        """Czas trwania zaplanowanej akwizycji w sekundach."""

        return (
            self.end_utc - self.start_utc
        ).total_seconds()

    @property
    def is_active(self) -> bool:
        """Informuje, czy wpis jest częścią aktywnego harmonogramu."""

        return self.status != ScheduleEntryStatus.CANCELLED


class Schedule(BaseModel):
    """Kompletny harmonogram dla określonego horyzontu planowania."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    schedule_id: str = Field(
        pattern=r"^SCHEDULE-[A-Z0-9-]+$",
    )

    name: str = Field(
        min_length=1,
        max_length=150,
    )

    horizon_start_utc: datetime
    horizon_end_utc: datetime

    created_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    algorithm: PlanningAlgorithm
    status: ScheduleStatus = ScheduleStatus.DRAFT

    entries: list[ScheduleEntry] = Field(
        default_factory=list,
    )

    frozen_until_utc: datetime | None = None

    memory_reserve_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    objective_value: float | None = None

    solver_runtime_s: float | None = Field(
        default=None,
        ge=0.0,
    )

    unassigned_request_ids: list[str] = Field(
        default_factory=list,
    )

    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator(
        "horizon_start_utc",
        "horizon_end_utc",
        "created_at_utc",
        "frozen_until_utc",
    )
    @classmethod
    def validate_utc_datetime(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Czas harmonogramu musi zawierać strefę czasową"
            )

        return value.astimezone(timezone.utc)

    @field_validator(
        "unassigned_request_ids",
        mode="before",
    )
    @classmethod
    def normalize_unassigned_request_ids(
        cls,
        value: Any,
    ) -> list[str]:
        if value is None:
            return []

        if not isinstance(value, list):
            raise ValueError(
                "unassigned_request_ids musi być listą"
            )

        normalized = [
            str(request_id).strip().upper()
            for request_id in value
        ]

        if any(not request_id for request_id in normalized):
            raise ValueError(
                "Identyfikator zlecenia nie może być pusty"
            )

        for request_id in normalized:
            if not re.fullmatch(
                r"REQ-[A-Z0-9-]+",
                request_id,
            ):
                raise ValueError(
                    f"Niepoprawny request_id: {request_id}"
                )

        if len(normalized) != len(set(normalized)):
            raise ValueError(
                "unassigned_request_ids nie może zawierać duplikatów"
            )

        return normalized

    @model_validator(mode="after")
    def validate_schedule_configuration(
        self,
    ) -> "Schedule":
        self._validate_horizon()
        self._validate_unique_identifiers()
        self._validate_entries_inside_horizon()
        self._validate_satellite_overlaps()
        self._validate_frozen_window()
        self._validate_unassigned_requests()
        self._validate_status()

        return self

    def _validate_horizon(self) -> None:
        if self.horizon_start_utc >= self.horizon_end_utc:
            raise ValueError(
                "horizon_start_utc musi być wcześniejsze "
                "niż horizon_end_utc"
            )

        if self.frozen_until_utc is not None:
            if not (
                self.horizon_start_utc
                <= self.frozen_until_utc
                <= self.horizon_end_utc
            ):
                raise ValueError(
                    "frozen_until_utc musi znajdować się "
                    "wewnątrz horyzontu planowania"
                )

    def _validate_unique_identifiers(self) -> None:
        entry_ids = [
            entry.entry_id
            for entry in self.entries
        ]

        opportunity_ids = [
            entry.opportunity_id
            for entry in self.entries
        ]

        if len(entry_ids) != len(set(entry_ids)):
            raise ValueError(
                "Harmonogram zawiera zduplikowane entry_id"
            )

        if len(opportunity_ids) != len(set(opportunity_ids)):
            raise ValueError(
                "Harmonogram zawiera zduplikowane opportunity_id"
            )

    def _validate_entries_inside_horizon(self) -> None:
        for entry in self.entries:
            if (
                entry.start_utc < self.horizon_start_utc
                or entry.end_utc > self.horizon_end_utc
            ):
                raise ValueError(
                    f"Wpis {entry.entry_id} znajduje się "
                    "poza horyzontem planowania"
                )

    def _validate_satellite_overlaps(self) -> None:
        entries_by_satellite: dict[str, list[ScheduleEntry]] = {}

        for entry in self.active_entries:
            entries_by_satellite.setdefault(
                entry.satellite_id,
                [],
            ).append(entry)

        for satellite_id, entries in entries_by_satellite.items():
            sorted_entries = sorted(
                entries,
                key=lambda item: item.start_utc,
            )

            for previous, current in zip(
                sorted_entries,
                sorted_entries[1:],
            ):
                if current.start_utc < previous.end_utc:
                    raise ValueError(
                        f"Nakładające się wpisy dla satelity "
                        f"{satellite_id}: {previous.entry_id} "
                        f"oraz {current.entry_id}"
                    )

    def _validate_frozen_window(self) -> None:
        frozen_entries = [
            entry
            for entry in self.active_entries
            if entry.status == ScheduleEntryStatus.FROZEN
        ]

        if self.frozen_until_utc is None:
            if frozen_entries:
                raise ValueError(
                    "Wpis FROZEN wymaga ustawienia frozen_until_utc"
                )

            return

        for entry in self.active_entries:
            if entry.start_utc < self.frozen_until_utc:
                if entry.status not in {
                    ScheduleEntryStatus.FROZEN,
                    ScheduleEntryStatus.EXECUTED,
                }:
                    raise ValueError(
                        f"Wpis {entry.entry_id} znajduje się "
                        "w zamrożonym okresie i musi mieć status "
                        "FROZEN albo EXECUTED"
                    )

            elif entry.status == ScheduleEntryStatus.FROZEN:
                raise ValueError(
                    f"Wpis {entry.entry_id} ma status FROZEN, "
                    "ale rozpoczyna się poza zamrożonym okresem"
                )

    def _validate_unassigned_requests(self) -> None:
        scheduled_ids = set(self.scheduled_request_ids)
        unassigned_ids = set(self.unassigned_request_ids)

        duplicated_ids = scheduled_ids & unassigned_ids

        if duplicated_ids:
            duplicated_text = ", ".join(
                sorted(duplicated_ids)
            )

            raise ValueError(
                "Zlecenie nie może być jednocześnie zaplanowane "
                f"i nieprzypisane: {duplicated_text}"
            )

    def _validate_status(self) -> None:
        if (
            self.status == ScheduleStatus.FINAL
            and self.objective_value is None
        ):
            raise ValueError(
                "Harmonogram FINAL wymaga objective_value"
            )

    @property
    def active_entries(self) -> list[ScheduleEntry]:
        """Zwraca wpisy inne niż CANCELLED."""

        return [
            entry
            for entry in self.entries
            if entry.is_active
        ]

    @property
    def total_acquisitions(self) -> int:
        """Liczba aktywnych akwizycji."""

        return len(self.active_entries)

    @property
    def total_duration_s(self) -> float:
        """Łączny czas aktywnych akwizycji."""

        return sum(
            entry.duration_s
            for entry in self.active_entries
        )

    @property
    def total_data_volume_mb(self) -> float:
        """Łączny rozmiar danych aktywnych akwizycji."""

        return sum(
            entry.estimated_data_volume_mb
            for entry in self.active_entries
        )

    @property
    def total_objective_contribution(self) -> float:
        """Suma wkładów wpisów do funkcji celu."""

        return sum(
            entry.objective_contribution
            for entry in self.active_entries
        )

    @property
    def scheduled_request_ids(self) -> list[str]:
        """Unikalne identyfikatory zaplanowanych zleceń."""

        return sorted(
            {
                entry.request_id
                for entry in self.active_entries
            }
        )

    @property
    def satellites_used(self) -> list[str]:
        """Unikalne identyfikatory użytych satelitów."""

        return sorted(
            {
                entry.satellite_id
                for entry in self.active_entries
            }
        )