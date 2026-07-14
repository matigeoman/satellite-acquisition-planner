from collections import Counter
from datetime import datetime, timezone

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import RequestMode, RequestStatus
from app.models.request import ObservationRequest


class ObservationRequestSet(BaseModel):
    """Zbiór zleceń dla jednego horyzontu planowania."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    request_set_id: str = Field(
        pattern=r"^REQSET-[A-Z0-9-]+$",
        description="Unikalny identyfikator zbioru zleceń.",
    )

    name: str = Field(
        min_length=1,
        max_length=150,
    )

    version: str = Field(
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$",
    )

    horizon_start_utc: datetime
    horizon_end_utc: datetime

    generated_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    requests: list[ObservationRequest] = Field(
        min_length=1,
    )

    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator(
        "horizon_start_utc",
        "horizon_end_utc",
        "generated_at_utc",
    )
    @classmethod
    def validate_utc_datetime(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Czas zbioru zleceń musi zawierać strefę czasową"
            )

        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_request_set_configuration(
        self,
    ) -> "ObservationRequestSet":
        self._validate_horizon()
        self._validate_unique_request_ids()
        self._validate_request_windows()

        return self

    def _validate_horizon(self) -> None:
        if self.horizon_start_utc >= self.horizon_end_utc:
            raise ValueError(
                "horizon_start_utc musi być wcześniejsze "
                "niż horizon_end_utc"
            )

    def _validate_unique_request_ids(self) -> None:
        request_ids = [
            request.request_id
            for request in self.requests
        ]

        duplicates = sorted(
            request_id
            for request_id, count in Counter(request_ids).items()
            if count > 1
        )

        if duplicates:
            raise ValueError(
                "Zbiór zawiera zduplikowane request_id: "
                + ", ".join(duplicates)
            )

    def _validate_request_windows(self) -> None:
        for request in self.requests:
            if (
                request.earliest_start_utc
                < self.horizon_start_utc
            ):
                raise ValueError(
                    f"Zlecenie {request.request_id} rozpoczyna się "
                    "przed horyzontem planowania"
                )

            if (
                request.latest_end_utc
                > self.horizon_end_utc
            ):
                raise ValueError(
                    f"Zlecenie {request.request_id} kończy się "
                    "po horyzoncie planowania"
                )

    @property
    def active_requests(self) -> list[ObservationRequest]:
        """Zwraca aktywne zlecenia."""

        return [
            request
            for request in self.requests
            if request.status == RequestStatus.ACTIVE
        ]

    @property
    def mandatory_requests(self) -> list[ObservationRequest]:
        """Zwraca aktywne zlecenia obowiązkowe."""

        return [
            request
            for request in self.active_requests
            if request.is_mandatory
        ]

    @property
    def requests_requiring_sar(self) -> list[ObservationRequest]:
        """Zwraca zlecenia wykorzystujące sensor SAR."""

        return [
            request
            for request in self.active_requests
            if request.requires_sar
        ]

    @property
    def requests_requiring_optical(
        self,
    ) -> list[ObservationRequest]:
        """Zwraca zlecenia wykorzystujące sensor optyczny."""

        return [
            request
            for request in self.active_requests
            if request.requires_optical
        ]

    @property
    def request_mode_counts(self) -> dict[str, int]:
        """Zwraca liczbę zleceń według trybu."""

        return dict(
            Counter(
                request.request_mode.value
                for request in self.requests
            )
        )

    @property
    def geometry_type_counts(self) -> dict[str, int]:
        """Zwraca liczbę geometrii Point i Polygon."""

        return dict(
            Counter(
                request.geometry.type
                for request in self.requests
            )
        )

    @property
    def dual_required_requests(
        self,
    ) -> list[ObservationRequest]:
        """Zwraca zlecenia wymagające dwóch akwizycji."""

        return [
            request
            for request in self.active_requests
            if request.request_mode == RequestMode.DUAL_REQUIRED
        ]

    def get_request(
        self,
        request_id: str,
    ) -> ObservationRequest:
        """Zwraca zlecenie na podstawie identyfikatora."""

        for request in self.requests:
            if request.request_id == request_id:
                return request

        raise KeyError(
            f"Nie znaleziono zlecenia: {request_id}"
        )