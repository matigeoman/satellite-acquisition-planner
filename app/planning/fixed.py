from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import ScheduleEntryStatus


@dataclass(frozen=True)
class FixedOpportunityAssignment:
    """Okazja, której decyzja pozostaje stała podczas przeplanowania."""

    opportunity_id: str
    status: ScheduleEntryStatus
    lock_reason: str | None = None

    def __post_init__(self) -> None:
        opportunity_id = self.opportunity_id.strip().upper()

        if not re.fullmatch(
            r"OPP-[A-Z0-9-]+",
            opportunity_id,
        ):
            raise ValueError(
                "Niepoprawny opportunity_id stałej okazji: "
                f"{self.opportunity_id}"
            )

        status = self.status

        if isinstance(status, str):
            try:
                status = ScheduleEntryStatus(
                    status.strip().upper()
                )
            except ValueError as error:
                raise ValueError(
                    "Nieobsługiwany status stałej okazji: "
                    f"{self.status}"
                ) from error

        if status not in {
            ScheduleEntryStatus.FROZEN,
            ScheduleEntryStatus.EXECUTED,
        }:
            raise ValueError(
                "Stała okazja musi mieć status FROZEN "
                "albo EXECUTED"
            )

        lock_reason = self.lock_reason

        if lock_reason is not None:
            lock_reason = lock_reason.strip()

            if not lock_reason:
                lock_reason = None

        if status == ScheduleEntryStatus.FROZEN:
            if lock_reason is None:
                raise ValueError(
                    "Stała okazja FROZEN wymaga lock_reason"
                )

            if len(lock_reason) > 500:
                raise ValueError(
                    "lock_reason nie może przekraczać 500 znaków"
                )

        elif lock_reason is not None:
            raise ValueError(
                "lock_reason może być ustawione wyłącznie "
                "dla statusu FROZEN"
            )

        object.__setattr__(
            self,
            "opportunity_id",
            opportunity_id,
        )
        object.__setattr__(
            self,
            "status",
            status,
        )
        object.__setattr__(
            self,
            "lock_reason",
            lock_reason,
        )
