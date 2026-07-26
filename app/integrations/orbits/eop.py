from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path


class EopDataKind(StrEnum):
    """Rodzaj rekordu w tabeli parametrów orientacji Ziemi."""

    OBSERVED = "OBSERVED"
    PREDICTED = "PREDICTED"


class EopParseError(ValueError):
    """Plik EOP ma nieobsługiwany albo uszkodzony format."""


class EopRangeError(ValueError):
    """Żądana chwila leży poza zakresem tabeli EOP."""


@dataclass(frozen=True, slots=True)
class EopSample:
    """Dobowy rekord EOP obowiązujący o 00:00 UTC."""

    timestamp_utc: datetime
    mjd: int
    polar_motion_x_arcsec: float
    polar_motion_y_arcsec: float
    ut1_minus_utc_s: float
    lod_s: float
    dpsi_arcsec: float
    deps_arcsec: float
    dx_arcsec: float
    dy_arcsec: float
    tai_minus_utc_s: int
    kind: EopDataKind


@dataclass(frozen=True, slots=True)
class EarthOrientationParameters:
    """Interpolowane parametry EOP dla jednej chwili UTC."""

    timestamp_utc: datetime
    polar_motion_x_arcsec: float
    polar_motion_y_arcsec: float
    ut1_minus_utc_s: float
    lod_s: float
    dx_arcsec: float
    dy_arcsec: float
    tai_minus_utc_s: int
    kind: EopDataKind
    interpolation_fraction: float


@dataclass(frozen=True, slots=True)
class EopTable:
    """Tabela EOP w formacie CelesTrak/AGI ``EOP-All-v1.1``."""

    samples: tuple[EopSample, ...]
    frame: str = "ITRF2020"
    updated_at_utc: datetime | None = None
    source_name: str | None = None
    _timestamps: tuple[datetime, ...] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if len(self.samples) < 2:
            raise EopParseError("Tabela EOP musi zawierać co najmniej dwa rekordy")
        timestamps = tuple(sample.timestamp_utc for sample in self.samples)
        if timestamps != tuple(sorted(timestamps)):
            raise EopParseError("Rekordy EOP nie są uporządkowane chronologicznie")
        if len(set(timestamps)) != len(timestamps):
            raise EopParseError("Tabela EOP zawiera zduplikowane daty")
        object.__setattr__(self, "_timestamps", timestamps)

    @property
    def start_utc(self) -> datetime:
        return self.samples[0].timestamp_utc

    @property
    def end_utc(self) -> datetime:
        return self.samples[-1].timestamp_utc

    @classmethod
    def from_file(cls, path: Path) -> "EopTable":
        source = Path(path)
        try:
            text = source.read_text(encoding="utf-8-sig")
        except OSError as error:
            raise EopParseError(f"Nie można odczytać pliku EOP {source}: {error}") from error
        return cls.from_text(text, source_name=str(source))

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        source_name: str | None = None,
    ) -> "EopTable":
        frame = "ITRF2020"
        updated_at: datetime | None = None
        kind: EopDataKind | None = None
        samples: list[EopSample] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("FRAME "):
                frame = line.removeprefix("FRAME ").strip() or frame
                continue
            if line.startswith("UPDATED "):
                updated_at = _parse_updated_timestamp(line.removeprefix("UPDATED "))
                continue
            if line == "BEGIN OBSERVED":
                kind = EopDataKind.OBSERVED
                continue
            if line == "END OBSERVED":
                kind = None
                continue
            if line == "BEGIN PREDICTED":
                kind = EopDataKind.PREDICTED
                continue
            if line == "END PREDICTED":
                kind = None
                continue
            if kind is None or line.startswith("#"):
                continue

            fields = line.split()
            if len(fields) < 13:
                raise EopParseError(
                    "Niepoprawny rekord EOP; oczekiwano co najmniej 13 pól: "
                    f"{raw_line!r}"
                )
            try:
                year, month, day, mjd = map(int, fields[:4])
                numeric = [float(value) for value in fields[4:12]]
                tai_minus_utc = int(fields[12])
            except ValueError as error:
                raise EopParseError(f"Niepoprawny rekord EOP: {raw_line!r}") from error

            samples.append(
                EopSample(
                    timestamp_utc=datetime(year, month, day, tzinfo=timezone.utc),
                    mjd=mjd,
                    polar_motion_x_arcsec=numeric[0],
                    polar_motion_y_arcsec=numeric[1],
                    ut1_minus_utc_s=numeric[2],
                    lod_s=numeric[3],
                    dpsi_arcsec=numeric[4],
                    deps_arcsec=numeric[5],
                    dx_arcsec=numeric[6],
                    dy_arcsec=numeric[7],
                    tai_minus_utc_s=tai_minus_utc,
                    kind=kind,
                )
            )

        if not samples:
            raise EopParseError("Nie znaleziono rekordów OBSERVED/PREDICTED w pliku EOP")
        return cls(
            samples=tuple(samples),
            frame=frame,
            updated_at_utc=updated_at,
            source_name=source_name,
        )

    def interpolate(self, timestamp_utc: datetime) -> EarthOrientationParameters:
        timestamp = _as_utc(timestamp_utc)
        if timestamp < self.start_utc or timestamp > self.end_utc:
            raise EopRangeError(
                "Chwila leży poza zakresem EOP: "
                f"{timestamp.isoformat()} nie należy do "
                f"[{self.start_utc.isoformat()}, {self.end_utc.isoformat()}]"
            )

        right_index = bisect_right(self._timestamps, timestamp)
        if right_index == 0:
            left = right = self.samples[0]
        elif right_index >= len(self.samples):
            left = right = self.samples[-1]
        else:
            left = self.samples[right_index - 1]
            right = self.samples[right_index]

        span_s = (right.timestamp_utc - left.timestamp_utc).total_seconds()
        fraction = 0.0 if span_s <= 0.0 else (
            (timestamp - left.timestamp_utc).total_seconds() / span_s
        )

        def linear(first: float, second: float) -> float:
            return first + (second - first) * fraction

        return EarthOrientationParameters(
            timestamp_utc=timestamp,
            polar_motion_x_arcsec=linear(
                left.polar_motion_x_arcsec,
                right.polar_motion_x_arcsec,
            ),
            polar_motion_y_arcsec=linear(
                left.polar_motion_y_arcsec,
                right.polar_motion_y_arcsec,
            ),
            ut1_minus_utc_s=linear(left.ut1_minus_utc_s, right.ut1_minus_utc_s),
            lod_s=linear(left.lod_s, right.lod_s),
            dx_arcsec=linear(left.dx_arcsec, right.dx_arcsec),
            dy_arcsec=linear(left.dy_arcsec, right.dy_arcsec),
            tai_minus_utc_s=left.tai_minus_utc_s,
            kind=(
                EopDataKind.PREDICTED
                if EopDataKind.PREDICTED in {left.kind, right.kind}
                else EopDataKind.OBSERVED
            ),
            interpolation_fraction=fraction,
        )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Czas EOP musi zawierać strefę czasową")
    return value.astimezone(timezone.utc)


def _parse_updated_timestamp(value: str) -> datetime | None:
    normalized = " ".join(value.split())
    for pattern in (
        "%Y %b %d %H:%M:%S %z",
        "%Y %b %d %H:%M:%S",
    ):
        try:
            parsed = datetime.strptime(normalized, pattern)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


__all__ = [
    "EarthOrientationParameters",
    "EopDataKind",
    "EopParseError",
    "EopRangeError",
    "EopSample",
    "EopTable",
]
