from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.version import __version__
from app.integrations.orbits.eop import EopParseError, EopTable


CELESTRAK_EOP_ENDPOINT = "https://celestrak.org/SpaceData/EOP-All-v1.1.txt"
DEFAULT_EOP_CACHE_TTL = timedelta(hours=12)
DEFAULT_EOP_MAX_STALE_AGE = timedelta(days=7)


class EopClientError(RuntimeError):
    """Błąd pobierania albo odczytu parametrów orientacji Ziemi."""


Transport = Callable[[str, float], bytes]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_transport(url: str, timeout_seconds: float) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "text/plain",
            "User-Agent": (
                f"SatelliteAcquisitionPlanner/{__version__} "
                "(educational earth-orientation integration)"
            ),
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise EopClientError(f"CelesTrak EOP zwrócił kod HTTP {status}")
        return response.read()


@dataclass(frozen=True, slots=True)
class EopQueryResult:
    table: EopTable
    fetched_at_utc: datetime
    request_url: str
    from_cache: bool
    is_stale: bool
    warning: str | None = None

    @property
    def age_seconds(self) -> float:
        return max(
            0.0,
            (datetime.now(timezone.utc) - self.fetched_at_utc).total_seconds(),
        )


class CelestrakEopClient:
    """Klient aktualnego pliku EOP z kontrolowanym cache dyskowym."""

    def __init__(
        self,
        *,
        cache_directory: Path,
        cache_ttl: timedelta = DEFAULT_EOP_CACHE_TTL,
        max_stale_age: timedelta = DEFAULT_EOP_MAX_STALE_AGE,
        timeout_seconds: float = 20.0,
        transport: Transport | None = None,
        now_provider: Callable[[], datetime] = _utc_now,
    ) -> None:
        if cache_ttl.total_seconds() < 0:
            raise ValueError("cache_ttl nie może być ujemne")
        if max_stale_age < cache_ttl:
            raise ValueError("max_stale_age nie może być krótsze niż cache_ttl")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds musi być dodatnie")
        self.cache_directory = Path(cache_directory)
        self.cache_ttl = cache_ttl
        self.max_stale_age = max_stale_age
        self.timeout_seconds = timeout_seconds
        self.transport = transport or _default_transport
        self.now_provider = now_provider

    @property
    def cache_path(self) -> Path:
        return self.cache_directory / "EOP-All-v1.1.txt"

    @property
    def metadata_path(self) -> Path:
        return self.cache_directory / "EOP-All-v1.1.fetched_at"

    def _read_cache(self) -> tuple[datetime, EopTable] | None:
        if not self.cache_path.exists() or not self.metadata_path.exists():
            return None
        try:
            fetched_at = datetime.fromisoformat(
                self.metadata_path.read_text(encoding="utf-8").strip()
            )
            if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            table = EopTable.from_file(self.cache_path)
        except (OSError, ValueError, EopParseError):
            return None
        return fetched_at.astimezone(timezone.utc), table

    def _write_cache(self, *, raw: bytes, fetched_at_utc: datetime) -> EopTable:
        try:
            decoded = raw.decode("utf-8-sig")
            table = EopTable.from_text(decoded, source_name=str(self.cache_path))
        except (UnicodeDecodeError, EopParseError) as error:
            raise EopClientError(f"Niepoprawny plik EOP: {error}") from error

        self.cache_directory.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(".txt.tmp")
        temporary.write_text(decoded, encoding="utf-8", newline="\n")
        temporary.replace(self.cache_path)
        self.metadata_path.write_text(
            fetched_at_utc.isoformat() + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return table

    def fetch(
        self,
        *,
        allow_network: bool = True,
        force_refresh: bool = False,
        allow_expired_cache: bool = False,
    ) -> EopQueryResult:
        if force_refresh and not allow_network:
            raise ValueError("force_refresh wymaga allow_network=True")

        now = self.now_provider().astimezone(timezone.utc)
        cached = self._read_cache()
        if cached is not None and not force_refresh:
            fetched_at, table = cached
            if now - fetched_at < self.cache_ttl:
                return EopQueryResult(
                    table=table,
                    fetched_at_utc=fetched_at,
                    request_url=CELESTRAK_EOP_ENDPOINT,
                    from_cache=True,
                    is_stale=False,
                )

        if not allow_network:
            if cached is None:
                raise EopClientError("Brak lokalnego cache EOP")
            fetched_at, table = cached
            age = now - fetched_at
            if age > self.max_stale_age and not allow_expired_cache:
                raise EopClientError(
                    "Lokalny cache EOP przekroczył maksymalny wiek "
                    f"{self.max_stale_age}."
                )
            return EopQueryResult(
                table=table,
                fetched_at_utc=fetched_at,
                request_url=CELESTRAK_EOP_ENDPOINT,
                from_cache=True,
                is_stale=True,
                warning="Użyto przeterminowanego cache EOP w trybie offline.",
            )

        try:
            raw = self.transport(CELESTRAK_EOP_ENDPOINT, self.timeout_seconds)
            table = self._write_cache(raw=raw, fetched_at_utc=now)
        except (EopClientError, HTTPError, URLError, TimeoutError, OSError) as error:
            if cached is None:
                raise EopClientError(f"Nie udało się pobrać EOP: {error}") from error
            fetched_at, table = cached
            age = now - fetched_at
            if age > self.max_stale_age and not allow_expired_cache:
                raise EopClientError(
                    "Nie udało się odświeżyć EOP, a cache przekroczył "
                    f"maksymalny wiek {self.max_stale_age}: {error}"
                ) from error
            return EopQueryResult(
                table=table,
                fetched_at_utc=fetched_at,
                request_url=CELESTRAK_EOP_ENDPOINT,
                from_cache=True,
                is_stale=True,
                warning=f"Nie udało się odświeżyć EOP. Użyto cache: {error}",
            )

        return EopQueryResult(
            table=table,
            fetched_at_utc=now,
            request_url=CELESTRAK_EOP_ENDPOINT,
            from_cache=False,
            is_stale=False,
        )


__all__ = [
    "CELESTRAK_EOP_ENDPOINT",
    "CelestrakEopClient",
    "DEFAULT_EOP_CACHE_TTL",
    "DEFAULT_EOP_MAX_STALE_AGE",
    "EopClientError",
    "EopQueryResult",
]
