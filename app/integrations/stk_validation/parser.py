from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import datetime, timezone
from typing import Iterable

import pandas as pd

from app.integrations.stk_validation.models import (
    ParsedStkAccessReport,
    ParsedStkAerReport,
    StkAccessInterval,
    StkAerSample,
)


_ACCESS_START_ALIASES = (
    "start time",
    "start time utcg",
    "access start",
    "start utc",
    "start",
    "begin time",
)
_ACCESS_END_ALIASES = (
    "stop time",
    "stop time utcg",
    "end time",
    "access stop",
    "access end",
    "end utc",
    "stop",
    "end",
)
_DURATION_ALIASES = (
    "duration",
    "duration sec",
    "duration seconds",
    "duration s",
)
_TIME_ALIASES = (
    "time",
    "time utcg",
    "epoch",
    "date time",
    "datetime",
)
_AZIMUTH_ALIASES = ("azimuth", "azimuth deg", "az")
_ELEVATION_ALIASES = ("elevation", "elevation deg", "el")
_RANGE_ALIASES = ("range", "range km", "slant range", "slant range km")
_SATELLITE_ALIASES = (
    "satellite",
    "satellite name",
    "from object",
    "from object name",
    "object",
)
_TARGET_ALIASES = (
    "target",
    "target name",
    "to object",
    "to object name",
    "area target",
)
_ID_ALIASES = ("access number", "access", "interval", "interval id", "id")


def _decode_payload(payload: bytes | str) -> str:
    if isinstance(payload, str):
        return payload
    for encoding in ("utf-8-sig", "utf-8", "cp1250", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Nie udało się odczytać kodowania raportu STK")


def _canonical(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    ascii_value = ascii_value.lower().replace("°", " deg ")
    ascii_value = re.sub(r"\([^)]*\)", " ", ascii_value)
    ascii_value = re.sub(r"[^a-z0-9]+", " ", ascii_value)
    return " ".join(ascii_value.split())


def _delimiter_for_line(line: str) -> str:
    candidates = (",", ";", "\t", "|")
    return max(candidates, key=line.count)


def _header_index(
    lines: list[str],
    *,
    required_alias_groups: tuple[tuple[str, ...], ...],
) -> tuple[int, str]:
    for index, line in enumerate(lines[:100]):
        if not line.strip():
            continue
        delimiter = _delimiter_for_line(line)
        if line.count(delimiter) < 2:
            continue
        columns = next(csv.reader([line], delimiter=delimiter))
        canonical_columns = {_canonical(column) for column in columns}
        if all(
            any(alias in canonical_columns for alias in alias_group)
            for alias_group in required_alias_groups
        ):
            return index, delimiter
    raise ValueError(
        "Nie znaleziono nagłówka raportu STK. Oczekiwane są kolumny czasu "
        "początku i końca albo Time/Azimuth/Elevation/Range."
    )


def _resolve_column(columns: Iterable[str], aliases: tuple[str, ...]) -> str | None:
    mapping = {_canonical(column): column for column in columns}
    for alias in aliases:
        if alias in mapping:
            return mapping[alias]
    for canonical_name, original in mapping.items():
        if any(alias in canonical_name for alias in aliases):
            return original
    return None


def _parse_datetime_utc(value: object) -> datetime:
    text = str(value).strip().strip('"').strip("'")
    text = re.sub(r"\s+(UTCG|UTC)$", "", text, flags=re.IGNORECASE).strip()
    text = text.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None

    if parsed is None:
        formats = (
            "%d %b %Y %H:%M:%S.%f",
            "%d %b %Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y %H:%M:%S.%f",
            "%m/%d/%Y %H:%M:%S",
        )
        for date_format in formats:
            try:
                parsed = datetime.strptime(text, date_format)
                break
            except ValueError:
                continue

    if parsed is None:
        timestamp = pd.to_datetime(text, errors="coerce", utc=True)
        if pd.isna(timestamp):
            raise ValueError(f"Niepoprawny czas STK: {value!r}")
        parsed = timestamp.to_pydatetime()

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_float(value: object) -> float:
    text = str(value).strip().replace(" ", "")
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    return float(text)


def _read_dataframe(
    payload: bytes | str,
    *,
    required_alias_groups: tuple[tuple[str, ...], ...],
) -> tuple[pd.DataFrame, str]:
    text = _decode_payload(payload)
    lines = text.splitlines()
    header_index, delimiter = _header_index(
        lines,
        required_alias_groups=required_alias_groups,
    )
    dataframe = pd.read_csv(
        io.StringIO("\n".join(lines[header_index:])),
        sep=delimiter,
        dtype=str,
        engine="python",
        on_bad_lines="skip",
    )
    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    dataframe = dataframe.dropna(how="all")
    return dataframe, delimiter


def parse_stk_access_report(payload: bytes | str) -> ParsedStkAccessReport:
    """Czyta typowy raport Access z Report & Graph Manager STK."""

    dataframe, delimiter = _read_dataframe(
        payload,
        required_alias_groups=(_ACCESS_START_ALIASES, _ACCESS_END_ALIASES),
    )
    start_column = _resolve_column(dataframe.columns, _ACCESS_START_ALIASES)
    end_column = _resolve_column(dataframe.columns, _ACCESS_END_ALIASES)
    duration_column = _resolve_column(dataframe.columns, _DURATION_ALIASES)
    id_column = _resolve_column(dataframe.columns, _ID_ALIASES)
    satellite_column = _resolve_column(dataframe.columns, _SATELLITE_ALIASES)
    target_column = _resolve_column(dataframe.columns, _TARGET_ALIASES)
    if start_column is None or end_column is None:
        raise ValueError("Raport nie zawiera kolumn Start Time i Stop Time")

    intervals: list[StkAccessInterval] = []
    warnings: list[str] = []
    for row_number, (_, row) in enumerate(dataframe.iterrows(), start=2):
        try:
            start = _parse_datetime_utc(row[start_column])
            end = _parse_datetime_utc(row[end_column])
        except (TypeError, ValueError):
            warnings.append(f"Pominięto niepoprawny wiersz Access {row_number}.")
            continue
        if end <= start:
            warnings.append(
                f"Pominięto wiersz Access {row_number}: koniec nie jest późniejszy."
            )
            continue
        duration = (end - start).total_seconds()
        if duration_column is not None and pd.notna(row[duration_column]):
            try:
                reported_duration = _parse_float(row[duration_column])
                if abs(reported_duration - duration) > 1.0:
                    warnings.append(
                        f"Wiersz {row_number}: Duration różni się od czasu "
                        "Start/Stop o ponad 1 s; użyto różnicy czasu."
                    )
            except (TypeError, ValueError):
                pass

        raw_id = row[id_column] if id_column is not None else len(intervals) + 1
        interval_id = f"STK-ACCESS-{str(raw_id).strip()}"
        intervals.append(
            StkAccessInterval(
                interval_id=interval_id,
                start_utc=start,
                end_utc=end,
                duration_s=duration,
                satellite_name=(
                    str(row[satellite_column]).strip()
                    if satellite_column is not None and pd.notna(row[satellite_column])
                    else None
                ),
                target_name=(
                    str(row[target_column]).strip()
                    if target_column is not None and pd.notna(row[target_column])
                    else None
                ),
                source_row=row_number,
            )
        )

    if not intervals:
        raise ValueError("Raport STK nie zawiera poprawnych przedziałów dostępu")
    intervals.sort(key=lambda interval: interval.start_utc)
    detected = {
        "start": start_column,
        "end": end_column,
    }
    if duration_column:
        detected["duration"] = duration_column
    if satellite_column:
        detected["satellite"] = satellite_column
    if target_column:
        detected["target"] = target_column
    return ParsedStkAccessReport(
        intervals=tuple(intervals),
        detected_columns=detected,
        delimiter=delimiter,
        warnings=tuple(warnings),
    )


def parse_stk_aer_report(payload: bytes | str) -> ParsedStkAerReport:
    """Czyta raport AER: Time, Azimuth, Elevation i Range."""

    dataframe, delimiter = _read_dataframe(
        payload,
        required_alias_groups=(
            _TIME_ALIASES,
            _AZIMUTH_ALIASES,
            _ELEVATION_ALIASES,
            _RANGE_ALIASES,
        ),
    )
    time_column = _resolve_column(dataframe.columns, _TIME_ALIASES)
    azimuth_column = _resolve_column(dataframe.columns, _AZIMUTH_ALIASES)
    elevation_column = _resolve_column(dataframe.columns, _ELEVATION_ALIASES)
    range_column = _resolve_column(dataframe.columns, _RANGE_ALIASES)
    if None in (time_column, azimuth_column, elevation_column, range_column):
        raise ValueError(
            "Raport AER wymaga kolumn Time, Azimuth, Elevation i Range"
        )

    samples: list[StkAerSample] = []
    warnings: list[str] = []
    for row_number, (_, row) in enumerate(dataframe.iterrows(), start=2):
        try:
            timestamp = _parse_datetime_utc(row[time_column])
            azimuth = _parse_float(row[azimuth_column])
            elevation = _parse_float(row[elevation_column])
            range_km = _parse_float(row[range_column])
        except (TypeError, ValueError):
            warnings.append(f"Pominięto niepoprawny wiersz AER {row_number}.")
            continue
        samples.append(
            StkAerSample(
                timestamp_utc=timestamp,
                azimuth_deg=azimuth % 360.0,
                elevation_deg=elevation,
                range_km=range_km,
                source_row=row_number,
            )
        )

    if not samples:
        raise ValueError("Raport STK nie zawiera poprawnych próbek AER")
    samples.sort(key=lambda sample: sample.timestamp_utc)
    return ParsedStkAerReport(
        samples=tuple(samples),
        detected_columns={
            "time": str(time_column),
            "azimuth": str(azimuth_column),
            "elevation": str(elevation_column),
            "range": str(range_column),
        },
        delimiter=delimiter,
        warnings=tuple(warnings),
    )
