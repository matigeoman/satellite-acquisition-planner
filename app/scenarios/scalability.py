from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.models.catalog import SystemCatalog
from app.models.enums import RequestMode, SensorType
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet


SOURCE_REQUEST_COUNT = 80
EXPANDED_REQUEST_COUNT = 100
OPPORTUNITIES_PER_REQUEST = 10

OPPORTUNITY_ID_PATTERN = re.compile(
    r"^OPP-(SAR|EO)-([0-9]+)$"
)


def build_scalability_source(
    *,
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
    target_request_count: int = EXPANDED_REQUEST_COUNT,
) -> tuple[
    ObservationRequestSet,
    AcquisitionOpportunitySet,
]:
    """
    Rozszerza scenariusz stresowy do wskazanej liczby zleceń.

    Dodatkowe zlecenia powstają przez deterministyczne, cykliczne
    klonowanie zbalansowanej listy zleceń źródłowych. Każdy klon
    zachowuje dziesięć okazji źródłowych, dzięki czemu można budować
    zagnieżdżone scenariusze od 80 do co najmniej 500 zleceń.
    """

    opportunity_set.validate_against(
        catalog,
        request_set,
    )

    if len(request_set.active_requests) != SOURCE_REQUEST_COUNT:
        raise ValueError(
            "Źródłowy scenariusz skalowalności musi "
            f"zawierać {SOURCE_REQUEST_COUNT} aktywnych zleceń"
        )

    if target_request_count < SOURCE_REQUEST_COUNT:
        raise ValueError(
            "target_request_count nie może być mniejsze od "
            f"{SOURCE_REQUEST_COUNT}"
        )

    request_counts = Counter(
        opportunity.request_id
        for opportunity in opportunity_set.opportunities
    )

    invalid_counts = {
        request_id: count
        for request_id, count in request_counts.items()
        if count != OPPORTUNITIES_PER_REQUEST
    }

    if invalid_counts:
        raise ValueError(
            "Każde zlecenie źródłowe musi posiadać "
            f"{OPPORTUNITIES_PER_REQUEST} okazji"
        )

    request_data = request_set.model_dump(mode="json")
    request_data["request_set_id"] = (
        f"REQSET-PL-SCALABILITY-{target_request_count:03d}"
    )
    request_data["name"] = (
        "Scenariusz skalowalności — "
        f"{target_request_count} zleceń"
    )
    request_data["version"] = "2.0.0"
    request_data["notes"] = (
        "Rozszerzony scenariusz stresowy przeznaczony "
        "do benchmarku skalowalności Greedy i CP-SAT."
    )

    expanded_requests = list(request_data["requests"])
    clone_mapping: dict[str, str] = {}

    clone_sources = [
        request
        for request in balanced_request_order(request_set)
        if not request.is_mandatory
    ]
    if not clone_sources:
        clone_sources = list(request_set.active_requests)

    clone_count = target_request_count - SOURCE_REQUEST_COUNT
    for clone_offset in range(clone_count):
        clone_index = SOURCE_REQUEST_COUNT + clone_offset + 1
        source_request = clone_sources[clone_offset % len(clone_sources)]
        request_label = _request_clone_label(source_request)
        new_request_id = (
            f"REQ-SCALE-{request_label}-{clone_index:04d}"
        )

        clone_mapping[new_request_id] = source_request.request_id

        clone_data = source_request.model_dump(mode="json")
        clone_data["request_id"] = new_request_id
        clone_data["name"] = (
            "Zlecenie skalowalności "
            f"{request_label} {clone_index:04d}"
        )
        clone_data["is_mandatory"] = False
        clone_data["external_reference"] = (
            f"SCALE-{clone_index:04d}"
        )
        clone_data["notes"] = (
            "SCALABILITY-CLONE|"
            f"SOURCE={source_request.request_id}"
        )
        expanded_requests.append(clone_data)

    request_data["requests"] = expanded_requests
    expanded_request_set = ObservationRequestSet.model_validate(request_data)

    opportunity_data = opportunity_set.model_dump(mode="json")
    opportunity_data["opportunity_set_id"] = (
        f"OPPSET-PL-SCALABILITY-{target_request_count:03d}"
    )
    opportunity_data["request_set_id"] = (
        expanded_request_set.request_set_id
    )
    opportunity_data["name"] = (
        "Okazje benchmarku skalowalności — "
        f"{target_request_count} zleceń"
    )
    opportunity_data["version"] = "2.0.0"
    opportunity_data["notes"] = (
        f"{target_request_count * OPPORTUNITIES_PER_REQUEST} okazji; "
        f"{OPPORTUNITIES_PER_REQUEST} okazji na każde zlecenie."
    )

    expanded_opportunities = list(opportunity_data["opportunities"])
    next_opportunity_number = _next_opportunity_number(opportunity_set)

    opportunities_by_request: dict[str, list[Any]] = {}
    for opportunity in opportunity_set.opportunities:
        opportunities_by_request.setdefault(
            opportunity.request_id, []
        ).append(opportunity)

    for new_request_id, source_request_id in clone_mapping.items():
        source_opportunities = sorted(
            opportunities_by_request[source_request_id],
            key=lambda opportunity: opportunity.opportunity_id,
        )

        if len(source_opportunities) != OPPORTUNITIES_PER_REQUEST:
            raise ValueError(
                f"Zlecenie {source_request_id} nie posiada "
                f"{OPPORTUNITIES_PER_REQUEST} okazji"
            )

        for source_opportunity in source_opportunities:
            sensor_label = (
                "SAR"
                if source_opportunity.sensor_type == SensorType.SAR
                else "EO"
            )
            clone_opportunity = source_opportunity.model_dump(mode="json")
            clone_opportunity["opportunity_id"] = (
                f"OPP-{sensor_label}-{next_opportunity_number:05d}"
            )
            clone_opportunity["request_id"] = new_request_id
            clone_opportunity["notes"] = (
                "SCALABILITY-CLONE|"
                f"SOURCE={source_opportunity.opportunity_id}"
            )
            expanded_opportunities.append(clone_opportunity)
            next_opportunity_number += 1

    opportunity_data["opportunities"] = expanded_opportunities
    expanded_opportunity_set = (
        AcquisitionOpportunitySet.model_validate(opportunity_data)
    )
    expanded_opportunity_set.validate_against(
        catalog, expanded_request_set
    )

    if len(expanded_request_set.active_requests) != target_request_count:
        raise ValueError(
            "Rozszerzony scenariusz nie zawiera "
            f"{target_request_count} zleceń"
        )

    expected_opportunity_count = (
        target_request_count * OPPORTUNITIES_PER_REQUEST
    )
    if (
        len(expanded_opportunity_set.opportunities)
        != expected_opportunity_count
    ):
        raise ValueError(
            "Rozszerzony scenariusz nie zawiera "
            f"{expected_opportunity_count} okazji"
        )

    return expanded_request_set, expanded_opportunity_set


def _request_clone_label(request: ObservationRequest) -> str:
    if request.request_mode == RequestMode.DUAL_REQUIRED:
        return "DUALR"
    if request.request_mode == RequestMode.DUAL_OPTIONAL:
        return "DUALO"
    if request.requires_sar and not request.requires_optical:
        return "SAR"
    if request.requires_optical and not request.requires_sar:
        return "EO"
    return "MIXED"

def build_scalability_subset(
    *,
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
    request_count: int,
) -> tuple[
    ObservationRequestSet,
    AcquisitionOpportunitySet,
]:
    """
    Buduje deterministyczny, zbalansowany podzbiór scenariusza.
    """

    if not 1 <= request_count <= len(
        request_set.active_requests
    ):
        raise ValueError(
            "request_count musi należeć do zakresu "
            f"[1, {len(request_set.active_requests)}]"
        )

    opportunity_set.validate_against(
        catalog,
        request_set,
    )

    ordered_requests = balanced_request_order(
        request_set
    )

    selected_requests = ordered_requests[
        :request_count
    ]

    selected_request_ids = {
        request.request_id
        for request in selected_requests
    }

    request_data = request_set.model_dump(
        mode="json"
    )

    request_data["request_set_id"] = (
        f"REQSET-PL-SCALE-{request_count:03d}"
    )
    request_data["name"] = (
        "Scenariusz skalowalności — "
        f"{request_count} zleceń"
    )
    request_data["notes"] = (
        "Deterministyczny, zbalansowany podzbiór "
        "scenariusza skalowalności."
    )
    request_data["requests"] = [
        request.model_dump(
            mode="json"
        )
        for request in selected_requests
    ]

    subset_request_set = (
        ObservationRequestSet.model_validate(
            request_data
        )
    )

    opportunity_data = opportunity_set.model_dump(
        mode="json"
    )

    opportunity_data["opportunity_set_id"] = (
        f"OPPSET-PL-SCALE-{request_count:03d}"
    )
    opportunity_data["request_set_id"] = (
        subset_request_set.request_set_id
    )
    opportunity_data["name"] = (
        "Okazje skalowalności — "
        f"{request_count} zleceń"
    )
    opportunity_data["notes"] = (
        f"{request_count * OPPORTUNITIES_PER_REQUEST} "
        "okazji benchmarkowych."
    )
    opportunity_data["opportunities"] = [
        opportunity.model_dump(
            mode="json"
        )
        for opportunity in opportunity_set.opportunities
        if opportunity.request_id
        in selected_request_ids
    ]

    subset_opportunity_set = (
        AcquisitionOpportunitySet.model_validate(
            opportunity_data
        )
    )

    subset_opportunity_set.validate_against(
        catalog,
        subset_request_set,
    )

    expected_opportunities = (
        request_count
        * OPPORTUNITIES_PER_REQUEST
    )

    if (
        len(subset_opportunity_set.opportunities)
        != expected_opportunities
    ):
        raise ValueError(
            "Podzbiór powinien zawierać "
            f"{expected_opportunities} okazji"
        )

    return (
        subset_request_set,
        subset_opportunity_set,
    )


def balanced_request_order(
    request_set: ObservationRequestSet,
) -> list[ObservationRequest]:
    """
    Buduje zagnieżdżoną kolejność zleceń.

    Wszystkie scenariusze 20/40/60/80/100 powstają jako
    prefiksy tej samej kolejności.
    """

    mandatory = sorted(
        request_set.mandatory_requests,
        key=lambda request: request.request_id,
    )

    mandatory_ids = {
        request.request_id
        for request in mandatory
    }

    buckets = [
        sorted(
            [
                request
                for request in request_set.active_requests
                if (
                    request.request_id
                    not in mandatory_ids
                    and request.request_mode
                    == RequestMode.SINGLE
                    and request.requires_sar
                    and not request.requires_optical
                )
            ],
            key=lambda request: request.request_id,
        ),
        sorted(
            [
                request
                for request in request_set.active_requests
                if (
                    request.request_id
                    not in mandatory_ids
                    and request.request_mode
                    == RequestMode.SINGLE
                    and request.requires_optical
                    and not request.requires_sar
                )
            ],
            key=lambda request: request.request_id,
        ),
        sorted(
            [
                request
                for request in request_set.active_requests
                if (
                    request.request_id
                    not in mandatory_ids
                    and request.request_mode
                    == RequestMode.DUAL_OPTIONAL
                )
            ],
            key=lambda request: request.request_id,
        ),
        sorted(
            [
                request
                for request in request_set.active_requests
                if (
                    request.request_id
                    not in mandatory_ids
                    and request.request_mode
                    == RequestMode.DUAL_REQUIRED
                )
            ],
            key=lambda request: request.request_id,
        ),
    ]

    ordered = list(
        mandatory
    )

    bucket_indices = [
        0
        for _ in buckets
    ]

    while True:
        added_request = False

        for bucket_number, bucket in enumerate(
            buckets
        ):
            bucket_index = bucket_indices[
                bucket_number
            ]

            if bucket_index >= len(bucket):
                continue

            ordered.append(
                bucket[bucket_index]
            )

            bucket_indices[
                bucket_number
            ] += 1

            added_request = True

        if not added_request:
            break

    ordered_ids = [
        request.request_id
        for request in ordered
    ]

    if len(ordered_ids) != len(set(ordered_ids)):
        raise ValueError(
            "Zbalansowana kolejność zawiera duplikaty"
        )

    if len(ordered) != len(
        request_set.active_requests
    ):
        raise ValueError(
            "Zbalansowana kolejność nie zawiera "
            "wszystkich aktywnych zleceń"
        )

    return ordered


def _select_clone_sources(
    *,
    request_set: ObservationRequestSet,
    sensor_type: SensorType,
    count: int,
) -> list[ObservationRequest]:
    sensor_label = (
        "SAR"
        if sensor_type == SensorType.SAR
        else "EO"
    )

    prefix = (
        f"REQ-STRESS-{sensor_label}-"
    )

    candidates = sorted(
        [
            request
            for request in request_set.active_requests
            if (
                request.request_mode
                == RequestMode.SINGLE
                and not request.is_mandatory
                and request.request_id.startswith(
                    prefix
                )
                and "-T" not in request.request_id
                and (
                    sensor_type
                    in request.requested_sensor_types
                )
            )
        ],
        key=lambda request: request.request_id,
    )

    if len(candidates) < count:
        raise ValueError(
            f"Brak {count} zleceń źródłowych "
            f"dla typu {sensor_type.value}"
        )

    return candidates[:count]


def _next_opportunity_number(
    opportunity_set: AcquisitionOpportunitySet,
) -> int:
    numbers = []

    for opportunity in opportunity_set.opportunities:
        match = OPPORTUNITY_ID_PATTERN.match(
            opportunity.opportunity_id
        )

        if match is None:
            raise ValueError(
                "Nieobsługiwany identyfikator okazji: "
                f"{opportunity.opportunity_id}"
            )

        numbers.append(
            int(match.group(2))
        )

    return max(numbers) + 1