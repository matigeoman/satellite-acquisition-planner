from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class StkAccessInterval:
    """Jedno okno dostępu zaimportowane z raportu STK."""

    interval_id: str
    start_utc: datetime
    end_utc: datetime
    duration_s: float
    satellite_name: str | None = None
    target_name: str | None = None
    source_row: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "interval_id": self.interval_id,
            "start_utc": self.start_utc.isoformat(),
            "end_utc": self.end_utc.isoformat(),
            "duration_s": self.duration_s,
            "satellite_name": self.satellite_name,
            "target_name": self.target_name,
            "source_row": self.source_row,
        }


@dataclass(frozen=True, slots=True)
class StkAerSample:
    """Próbka Azimuth/Elevation/Range z raportu STK."""

    timestamp_utc: datetime
    azimuth_deg: float
    elevation_deg: float
    range_km: float
    source_row: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "azimuth_deg": self.azimuth_deg,
            "elevation_deg": self.elevation_deg,
            "range_km": self.range_km,
            "source_row": self.source_row,
        }


@dataclass(frozen=True, slots=True)
class ParsedStkAccessReport:
    """Znormalizowany raport Access oraz informacje diagnostyczne parsera."""

    intervals: tuple[StkAccessInterval, ...]
    detected_columns: dict[str, str]
    delimiter: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedStkAerReport:
    """Znormalizowany raport AER oraz informacje diagnostyczne parsera."""

    samples: tuple[StkAerSample, ...]
    detected_columns: dict[str, str]
    delimiter: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MatchedAccessInterval:
    """Dopasowanie jednego okna modelu do jednego okna raportu STK."""

    model_window_id: str
    stk_interval_id: str
    model_start_utc: datetime
    stk_start_utc: datetime
    model_end_utc: datetime
    stk_end_utc: datetime
    model_duration_s: float
    stk_duration_s: float
    start_error_s: float
    end_error_s: float
    duration_error_s: float
    overlap_s: float
    overlap_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_window_id": self.model_window_id,
            "stk_interval_id": self.stk_interval_id,
            "model_start_utc": self.model_start_utc.isoformat(),
            "stk_start_utc": self.stk_start_utc.isoformat(),
            "model_end_utc": self.model_end_utc.isoformat(),
            "stk_end_utc": self.stk_end_utc.isoformat(),
            "model_duration_s": self.model_duration_s,
            "stk_duration_s": self.stk_duration_s,
            "start_error_s": self.start_error_s,
            "end_error_s": self.end_error_s,
            "duration_error_s": self.duration_error_s,
            "overlap_s": self.overlap_s,
            "overlap_ratio": self.overlap_ratio,
        }


@dataclass(frozen=True, slots=True)
class ErrorStatistics:
    """Podstawowe statystyki błędu podpisane jednostką."""

    count: int
    mean_error: float
    mean_absolute_error: float
    root_mean_square_error: float
    median_absolute_error: float
    maximum_absolute_error: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "mean_error": self.mean_error,
            "mean_absolute_error": self.mean_absolute_error,
            "root_mean_square_error": self.root_mean_square_error,
            "median_absolute_error": self.median_absolute_error,
            "maximum_absolute_error": self.maximum_absolute_error,
        }


@dataclass(frozen=True, slots=True)
class AccessValidationResult:
    """Wynik porównania przedziałów modelu własnego i STK."""

    matched: tuple[MatchedAccessInterval, ...]
    unmatched_model_window_ids: tuple[str, ...]
    unmatched_stk_interval_ids: tuple[str, ...]
    start_error_statistics_s: ErrorStatistics
    end_error_statistics_s: ErrorStatistics
    duration_error_statistics_s: ErrorStatistics
    mean_overlap_ratio: float
    tolerance_s: float

    @property
    def model_window_count(self) -> int:
        return len(self.matched) + len(self.unmatched_model_window_ids)

    @property
    def stk_interval_count(self) -> int:
        return len(self.matched) + len(self.unmatched_stk_interval_ids)

    @property
    def match_rate(self) -> float:
        denominator = max(self.model_window_count, self.stk_interval_count, 1)
        return len(self.matched) / denominator

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": [match.to_dict() for match in self.matched],
            "unmatched_model_window_ids": list(self.unmatched_model_window_ids),
            "unmatched_stk_interval_ids": list(self.unmatched_stk_interval_ids),
            "start_error_statistics_s": self.start_error_statistics_s.to_dict(),
            "end_error_statistics_s": self.end_error_statistics_s.to_dict(),
            "duration_error_statistics_s": (
                self.duration_error_statistics_s.to_dict()
            ),
            "mean_overlap_ratio": self.mean_overlap_ratio,
            "tolerance_s": self.tolerance_s,
            "match_rate": self.match_rate,
            "model_window_count": self.model_window_count,
            "stk_interval_count": self.stk_interval_count,
        }


@dataclass(frozen=True, slots=True)
class MatchedAerSample:
    """Porównanie geometrii AER w jednej chwili."""

    timestamp_utc: datetime
    model_timestamp_utc: datetime
    time_offset_s: float
    model_azimuth_deg: float
    stk_azimuth_deg: float
    azimuth_error_deg: float
    model_elevation_deg: float
    stk_elevation_deg: float
    elevation_error_deg: float
    model_range_km: float
    stk_range_km: float
    range_error_km: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "model_timestamp_utc": self.model_timestamp_utc.isoformat(),
            "time_offset_s": self.time_offset_s,
            "model_azimuth_deg": self.model_azimuth_deg,
            "stk_azimuth_deg": self.stk_azimuth_deg,
            "azimuth_error_deg": self.azimuth_error_deg,
            "model_elevation_deg": self.model_elevation_deg,
            "stk_elevation_deg": self.stk_elevation_deg,
            "elevation_error_deg": self.elevation_error_deg,
            "model_range_km": self.model_range_km,
            "stk_range_km": self.stk_range_km,
            "range_error_km": self.range_error_km,
        }


@dataclass(frozen=True, slots=True)
class AerValidationResult:
    """Wynik porównania próbek AER z geometrią własnego modelu."""

    matched: tuple[MatchedAerSample, ...]
    unmatched_stk_sample_count: int
    azimuth_error_statistics_deg: ErrorStatistics
    elevation_error_statistics_deg: ErrorStatistics
    range_error_statistics_km: ErrorStatistics
    time_tolerance_s: float

    @property
    def match_rate(self) -> float:
        denominator = len(self.matched) + self.unmatched_stk_sample_count
        return len(self.matched) / max(denominator, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": [match.to_dict() for match in self.matched],
            "unmatched_stk_sample_count": self.unmatched_stk_sample_count,
            "azimuth_error_statistics_deg": (
                self.azimuth_error_statistics_deg.to_dict()
            ),
            "elevation_error_statistics_deg": (
                self.elevation_error_statistics_deg.to_dict()
            ),
            "range_error_statistics_km": (
                self.range_error_statistics_km.to_dict()
            ),
            "time_tolerance_s": self.time_tolerance_s,
            "match_rate": self.match_rate,
        }
