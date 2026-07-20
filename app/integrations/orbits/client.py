from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.integrations.orbits.models import (
    CelestrakQueryResult,
    PublicOrbitRecord,
)


CELESTRAK_GP_ENDPOINT = "https://celestrak.org/NORAD/elements/gp.php"
DEFAULT_CACHE_TTL = timedelta(hours=2)
_CACHE_SCHEMA_VERSION = 1


class CelestrakClientError(RuntimeError):
    """Błąd pobierania lub walidacji publicznych danych GP/OMM."""


Transport = Callable[[str, float], bytes]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_transport(url: str, timeout_seconds: float) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "SatelliteAcquisitionPlanner/1.0 "
                "(educational public-orbit integration)"
            ),
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise CelestrakClientError(
                f"CelesTrak zwrócił kod HTTP {status}"
            )
        return response.read()


class CelestrakClient:
    """Klient GP/OMM z dyskowym cache zgodnym z polityką CelesTrak."""

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
    def build_name_query_url(name: str) -> str:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Nazwa wyszukiwania nie może być pusta")
        query = urlencode({"NAME": normalized, "FORMAT": "JSON"})
        return f"{CELESTRAK_GP_ENDPOINT}?{query}"

    def _cache_path(self, name: str) -> Path:
        slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
        if not slug:
            raise ValueError("Nie można zbudować nazwy pliku cache")
        return self.cache_directory / f"{slug}.omm.json"

    def _read_cache(self, name: str) -> tuple[datetime, list[dict[str, Any]]] | None:
        path = self._cache_path(name)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != _CACHE_SCHEMA_VERSION:
                return None
            fetched_at = datetime.fromisoformat(payload["fetched_at_utc"])
            if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            records = payload["records"]
            if not isinstance(records, list):
                return None
            return fetched_at.astimezone(timezone.utc), records
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def _write_cache(
        self,
        *,
        name: str,
        fetched_at_utc: datetime,
        records: list[dict[str, Any]],
    ) -> None:
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(name)
        temporary = path.with_suffix(path.suffix + ".tmp")
        payload = {
            "schema_version": _CACHE_SCHEMA_VERSION,
            "query_name": name,
            "fetched_at_utc": fetched_at_utc.isoformat(),
            "records": records,
        }
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _parse_records(payload: Any) -> tuple[PublicOrbitRecord, ...]:
        if not isinstance(payload, list):
            raise CelestrakClientError(
                "CelesTrak nie zwrócił listy rekordów OMM JSON"
            )

        records: list[PublicOrbitRecord] = []
        errors: list[str] = []
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                errors.append(f"rekord {index}: nie jest obiektem JSON")
                continue
            try:
                records.append(PublicOrbitRecord.from_omm(item))
            except ValueError as error:
                errors.append(f"rekord {index}: {error}")

        if not records:
            details = "; ".join(errors[:3])
            raise CelestrakClientError(
                "Brak poprawnych rekordów OMM"
                + (f": {details}" if details else "")
            )
        return tuple(records)

    def _result_from_cache(
        self,
        *,
        name: str,
        cached: tuple[datetime, list[dict[str, Any]]],
        request_url: str,
        stale: bool,
        warning: str | None = None,
    ) -> CelestrakQueryResult:
        fetched_at, raw_records = cached
        return CelestrakQueryResult(
            query_name=name,
            records=self._parse_records(raw_records),
            fetched_at_utc=fetched_at,
            request_url=request_url,
            from_cache=True,
            is_stale=stale,
            warning=warning,
        )

    def fetch_by_name(
        self,
        name: str,
        *,
        allow_network: bool = True,
        force_refresh: bool = False,
    ) -> CelestrakQueryResult:
        """Pobiera rekordy OMM, korzystając z cache lub wymuszając sieć.

        ``force_refresh`` omija świeży cache, ale nadal używa go jako
        bezpiecznego fallbacku, jeśli CelesTrak nie odpowiada.
        """

        if force_refresh and not allow_network:
            raise ValueError("force_refresh wymaga allow_network=True")

        normalized = name.strip()
        request_url = self.build_name_query_url(normalized)
        now = self.now_provider().astimezone(timezone.utc)
        cached = self._read_cache(normalized)

        if cached is not None and not force_refresh:
            fetched_at, _records = cached
            if now - fetched_at < self.cache_ttl:
                return self._result_from_cache(
                    name=normalized,
                    cached=cached,
                    request_url=request_url,
                    stale=False,
                )

        if not allow_network:
            if cached is None:
                raise CelestrakClientError(
                    f"Brak lokalnego cache dla zapytania {normalized!r}"
                )
            return self._result_from_cache(
                name=normalized,
                cached=cached,
                request_url=request_url,
                stale=True,
                warning="Użyto przeterminowanego cache w trybie offline.",
            )

        try:
            raw = self.transport(request_url, self.timeout_seconds)
            decoded = raw.decode("utf-8-sig")
            payload = json.loads(decoded)
            records = self._parse_records(payload)
        except (
            CelestrakClientError,
            HTTPError,
            URLError,
            TimeoutError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            OSError,
        ) as error:
            if cached is not None:
                cache_is_stale = now - cached[0] >= self.cache_ttl
                return self._result_from_cache(
                    name=normalized,
                    cached=cached,
                    request_url=request_url,
                    stale=cache_is_stale,
                    warning=(
                        "Nie udało się odświeżyć CelesTrak. "
                        f"Użyto ostatniego cache: {error}"
                    ),
                )
            raise CelestrakClientError(
                f"Nie udało się pobrać danych CelesTrak: {error}"
            ) from error

        raw_records = [dict(record.raw_omm) for record in records]
        self._write_cache(
            name=normalized,
            fetched_at_utc=now,
            records=raw_records,
        )
        return CelestrakQueryResult(
            query_name=normalized,
            records=records,
            fetched_at_utc=now,
            request_url=request_url,
            from_cache=False,
            is_stale=False,
        )
