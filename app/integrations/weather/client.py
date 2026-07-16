from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.integrations.weather.models import (
    HourlyCloudSample,
    WeatherForecastResult,
    WeatherLocation,
    WeatherPointForecast,
)


OPEN_METEO_FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
DEFAULT_CACHE_TTL = timedelta(hours=1)
_CACHE_SCHEMA_VERSION = 1
_HOURLY_VARIABLES = (
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
)


class OpenMeteoClientError(RuntimeError):
    """Błąd pobrania albo walidacji prognozy Open-Meteo."""


Transport = Callable[[str, float], bytes]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Czas musi zawierać strefę czasową")
    return value.astimezone(timezone.utc)


def _default_transport(url: str, timeout_seconds: float) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "SatelliteAcquisitionPlanner/1.0 "
                "(educational weather integration)"
            ),
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise OpenMeteoClientError(
                f"Open-Meteo zwrócił kod HTTP {status}"
            )
        return response.read()


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise OpenMeteoClientError("Prognoza zawiera niepoprawny czas")
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _numeric_list(payload: dict[str, Any], key: str, length: int) -> list[float]:
    raw = payload.get(key)
    if not isinstance(raw, list) or len(raw) != length:
        raise OpenMeteoClientError(
            f"Prognoza nie zawiera poprawnej serii {key}"
        )
    values: list[float] = []
    for value in raw:
        if value is None:
            raise OpenMeteoClientError(f"Seria {key} zawiera null")
        number = float(value)
        values.append(min(100.0, max(0.0, number)))
    return values


class OpenMeteoClient:
    """Klient prognozy zachmurzenia z dyskowym cache."""

    def __init__(
        self,
        *,
        cache_directory: Path,
        cache_ttl: timedelta = DEFAULT_CACHE_TTL,
        timeout_seconds: float = 20.0,
        transport: Transport | None = None,
        now_provider: Callable[[], datetime] = _utc_now,
    ) -> None:
        if cache_ttl.total_seconds() < 0:
            raise ValueError("cache_ttl nie może być ujemne")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds musi być dodatnie")
        self.cache_directory = Path(cache_directory)
        self.cache_ttl = cache_ttl
        self.timeout_seconds = timeout_seconds
        self.transport = transport or _default_transport
        self.now_provider = now_provider

    @staticmethod
    def build_url(
        locations: Sequence[WeatherLocation],
        *,
        start_utc: datetime,
        end_utc: datetime,
    ) -> str:
        if not locations:
            raise ValueError("Wymagany jest co najmniej jeden punkt pogody")
        start = _as_utc(start_utc)
        end = _as_utc(end_utc)
        if start >= end:
            raise ValueError("start_utc musi być wcześniejsze niż end_utc")

        query = urlencode(
            {
                "latitude": ",".join(
                    f"{location.latitude_deg:.6f}" for location in locations
                ),
                "longitude": ",".join(
                    f"{location.longitude_deg:.6f}" for location in locations
                ),
                "hourly": ",".join(_HOURLY_VARIABLES),
                "timeformat": "iso8601",
                "timezone": "UTC",
                "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
                "end_hour": end.strftime("%Y-%m-%dT%H:%M"),
            }
        )
        return f"{OPEN_METEO_FORECAST_ENDPOINT}?{query}"

    def _cache_path(self, request_url: str) -> Path:
        digest = hashlib.sha256(request_url.encode("utf-8")).hexdigest()[:24]
        return self.cache_directory / f"cloud-{digest}.json"

    def _read_cache(
        self,
        request_url: str,
    ) -> tuple[datetime, Any] | None:
        path = self._cache_path(request_url)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != _CACHE_SCHEMA_VERSION:
                return None
            fetched_at = _parse_timestamp(payload["fetched_at_utc"])
            return fetched_at, payload["response"]
        except (OSError, TypeError, KeyError, ValueError, json.JSONDecodeError):
            return None

    def _write_cache(
        self,
        *,
        request_url: str,
        fetched_at_utc: datetime,
        response_payload: Any,
    ) -> None:
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(request_url)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": _CACHE_SCHEMA_VERSION,
                    "fetched_at_utc": fetched_at_utc.isoformat(),
                    "request_url": request_url,
                    "response": response_payload,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _parse_single_forecast(
        payload: Any,
        location: WeatherLocation,
    ) -> WeatherPointForecast:
        if not isinstance(payload, dict):
            raise OpenMeteoClientError("Odpowiedź punktowa nie jest JSON object")
        hourly = payload.get("hourly")
        if not isinstance(hourly, dict):
            reason = payload.get("reason")
            if reason:
                raise OpenMeteoClientError(str(reason))
            raise OpenMeteoClientError("Odpowiedź nie zawiera sekcji hourly")
        raw_times = hourly.get("time")
        if not isinstance(raw_times, list) or not raw_times:
            raise OpenMeteoClientError("Odpowiedź nie zawiera osi czasu")
        timestamps = [_parse_timestamp(value) for value in raw_times]
        count = len(timestamps)
        total = _numeric_list(hourly, "cloud_cover", count)
        low = _numeric_list(hourly, "cloud_cover_low", count)
        middle = _numeric_list(hourly, "cloud_cover_mid", count)
        high = _numeric_list(hourly, "cloud_cover_high", count)
        samples = tuple(
            HourlyCloudSample(
                timestamp_utc=timestamps[index],
                cloud_cover_percent=total[index],
                cloud_cover_low_percent=low[index],
                cloud_cover_mid_percent=middle[index],
                cloud_cover_high_percent=high[index],
            )
            for index in range(count)
        )
        elevation = payload.get("elevation")
        return WeatherPointForecast(
            location=location,
            latitude_deg=float(payload.get("latitude", location.latitude_deg)),
            longitude_deg=float(payload.get("longitude", location.longitude_deg)),
            elevation_m=None if elevation is None else float(elevation),
            timezone_name=str(payload.get("timezone", "UTC")),
            samples=samples,
        )

    @classmethod
    def _parse_response(
        cls,
        payload: Any,
        locations: Sequence[WeatherLocation],
    ) -> tuple[WeatherPointForecast, ...]:
        if len(locations) == 1 and isinstance(payload, dict):
            entries = [payload]
        elif isinstance(payload, list):
            entries = payload
        else:
            raise OpenMeteoClientError(
                "Niepoprawny format odpowiedzi dla wielu lokalizacji"
            )
        if len(entries) != len(locations):
            raise OpenMeteoClientError(
                "Liczba prognoz nie odpowiada liczbie punktów AOI"
            )
        return tuple(
            cls._parse_single_forecast(entry, location)
            for entry, location in zip(entries, locations, strict=True)
        )

    def _from_cache(
        self,
        *,
        cached: tuple[datetime, Any],
        request_url: str,
        locations: Sequence[WeatherLocation],
        stale: bool,
        warning: str | None = None,
    ) -> WeatherForecastResult:
        fetched_at, payload = cached
        return WeatherForecastResult(
            forecasts=self._parse_response(payload, locations),
            fetched_at_utc=fetched_at,
            request_url=request_url,
            from_cache=True,
            is_stale=stale,
            warning=warning,
        )

    def fetch_cloud_forecast(
        self,
        locations: Sequence[WeatherLocation],
        *,
        start_utc: datetime,
        end_utc: datetime,
        allow_network: bool = True,
    ) -> WeatherForecastResult:
        """Pobiera godzinowe zachmurzenie dla maksymalnie 20 punktów AOI."""

        normalized_locations = tuple(locations)
        if not 1 <= len(normalized_locations) <= 20:
            raise ValueError("Liczba punktów pogody musi należeć do [1, 20]")
        request_url = self.build_url(
            normalized_locations,
            start_utc=start_utc,
            end_utc=end_utc,
        )
        now = _as_utc(self.now_provider())
        cached = self._read_cache(request_url)
        if cached is not None and now - cached[0] < self.cache_ttl:
            return self._from_cache(
                cached=cached,
                request_url=request_url,
                locations=normalized_locations,
                stale=False,
            )
        if not allow_network:
            if cached is None:
                raise OpenMeteoClientError(
                    "Brak lokalnego cache prognozy dla wybranego AOI i czasu"
                )
            return self._from_cache(
                cached=cached,
                request_url=request_url,
                locations=normalized_locations,
                stale=True,
                warning="Użyto przeterminowanego cache pogody w trybie offline.",
            )

        try:
            raw = self.transport(request_url, self.timeout_seconds)
            payload = json.loads(raw.decode("utf-8-sig"))
            forecasts = self._parse_response(payload, normalized_locations)
        except (
            OpenMeteoClientError,
            HTTPError,
            URLError,
            TimeoutError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            OSError,
        ) as error:
            if cached is not None:
                return self._from_cache(
                    cached=cached,
                    request_url=request_url,
                    locations=normalized_locations,
                    stale=True,
                    warning=(
                        "Nie udało się odświeżyć Open-Meteo. "
                        f"Użyto ostatniego cache: {error}"
                    ),
                )
            raise OpenMeteoClientError(
                f"Nie udało się pobrać prognozy Open-Meteo: {error}"
            ) from error

        self._write_cache(
            request_url=request_url,
            fetched_at_utc=now,
            response_payload=payload,
        )
        return WeatherForecastResult(
            forecasts=forecasts,
            fetched_at_utc=now,
            request_url=request_url,
            from_cache=False,
            is_stale=False,
        )
