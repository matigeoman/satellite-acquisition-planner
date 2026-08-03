from __future__ import annotations

from typing import (
    Any,
    Mapping,
    MutableMapping,
    Protocol,
    TypeAlias,
    TypeVar,
    overload,
)


StateKey = str | int
_DefaultT = TypeVar("_DefaultT")


class _SessionStateReader(Protocol):
    """Minimalny kontrakt odczytu stanu sesji Streamlit."""

    @overload
    def get(
        self,
        key: StateKey,
        /,
    ) -> Any | None:
        ...

    @overload
    def get(
        self,
        key: StateKey,
        default: _DefaultT,
        /,
    ) -> Any | _DefaultT:
        ...


class _SessionStateStore(_SessionStateReader, Protocol):
    """Minimalny kontrakt zapisu stanu sesji Streamlit."""

    def __setitem__(
        self,
        key: StateKey,
        value: Any,
        /,
    ) -> None:
        ...

    @overload
    def pop(
        self,
        key: StateKey,
        /,
    ) -> Any:
        ...

    @overload
    def pop(
        self,
        key: StateKey,
        default: _DefaultT,
        /,
    ) -> Any | _DefaultT:
        ...


StateReader: TypeAlias = Mapping[str, Any] | _SessionStateReader
StateStore: TypeAlias = MutableMapping[str, Any] | _SessionStateStore


__all__ = ["StateReader", "StateStore"]
