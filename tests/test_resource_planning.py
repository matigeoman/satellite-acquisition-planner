import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.models.catalog import SystemCatalog
from app.models.downlink import DownlinkOpportunity
from app.models.downlink_set import DownlinkOpportunitySet
from app.models.opportunity import AcquisitionOpportunity
from app.planning.resources import allocate_downlinks_greedily


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIRECTORY = PROJECT_ROOT / "data" / "scenarios" / "example"


def _small_catalog() -> SystemCatalog:
    data = json.loads((EXAMPLE_DIRECTORY / "system.json").read_text(encoding="utf-8"))
    data["orbits"] = [data["orbits"][0]]
    data["sensors"] = [data["sensors"][0]]
    satellite = deepcopy(data["satellites"][0])
    satellite["memory_capacity_mb"] = 1000.0
    satellite["initial_memory_usage_mb"] = 0.0
    data["satellites"] = [satellite]
    data["ground_stations"] = [data["ground_stations"][0]]
    return SystemCatalog.model_validate(data)


def _acquisition(identifier: str, end_utc: str) -> AcquisitionOpportunity:
    source = json.loads(
        (EXAMPLE_DIRECTORY / "opportunities.json").read_text(encoding="utf-8")
    )["opportunities"][0]
    source.update(
        {
            "opportunity_id": identifier,
            "request_id": f"REQ-{identifier.removeprefix('OPP-')}",
            "start_utc": end_utc.replace(":10:00Z", ":09:30Z"),
            "end_utc": end_utc,
            "estimated_data_volume_mb": 600.0,
        }
    )
    return AcquisitionOpportunity.model_validate(source)


def _window(identifier: str, start_utc: str, end_utc: str) -> DownlinkOpportunity:
    return DownlinkOpportunity(
        downlink_opportunity_id=identifier,
        satellite_id="SAR-01",
        ground_station_id="GS-WARSAW",
        start_utc=start_utc,
        end_utc=end_utc,
        data_rate_mbps=160.0,
        link_efficiency=1.0,
    )


def _set(windows: list[DownlinkOpportunity]) -> DownlinkOpportunitySet:
    return DownlinkOpportunitySet(
        downlink_set_id="DLOSET-RESOURCE-TEST",
        name="Test zasobów",
        version="1.3.0",
        catalog_id="CATALOG-PL-MODEL",
        horizon_start_utc="2026-07-15T00:00:00Z",
        horizon_end_utc="2026-07-16T00:00:00Z",
        generated_at_utc="2026-07-14T00:00:00Z",
        opportunities=windows,
    )


def test_downlink_can_make_total_acquired_data_exceed_memory_capacity() -> None:
    catalog = _small_catalog()
    acquisitions = [
        _acquisition("OPP-RESOURCE-A", "2026-07-15T01:10:00Z"),
        _acquisition("OPP-RESOURCE-B", "2026-07-15T02:10:00Z"),
    ]
    downlink_set = _set(
        [
            _window(
                "DLO-RESOURCE-A",
                "2026-07-15T01:20:00Z",
                "2026-07-15T01:30:00Z",
            ),
            _window(
                "DLO-RESOURCE-B",
                "2026-07-15T02:20:00Z",
                "2026-07-15T02:30:00Z",
            ),
        ]
    )

    result = allocate_downlinks_greedily(
        catalog=catalog,
        acquisitions=acquisitions,
        downlink_set=downlink_set,
        memory_reserve_ratio=0.0,
        require_full_downlink=True,
        allow_simultaneous_imaging_downlink=False,
        downlink_capacity_reserve_ratio=0.0,
    )

    summary = result.summaries[0]
    assert result.feasible
    assert summary.acquired_data_mb == pytest.approx(1200.0)
    assert summary.peak_memory_usage_mb == pytest.approx(600.0)
    assert summary.final_memory_usage_mb == pytest.approx(0.0)
    assert summary.downlinked_data_mb == pytest.approx(1200.0)
    assert len(result.downlink_entries) == 2
    assert result.memory_timeline[0].timestamp_utc == downlink_set.horizon_start_utc
    assert result.downlink_entries[0].delivered_reference_ids == [
        "OPP-RESOURCE-A"
    ]


def test_late_downlink_does_not_hide_earlier_memory_overflow() -> None:
    catalog = _small_catalog()
    acquisitions = [
        _acquisition("OPP-RESOURCE-A", "2026-07-15T01:10:00Z"),
        _acquisition("OPP-RESOURCE-B", "2026-07-15T02:10:00Z"),
    ]
    downlink_set = _set(
        [
            _window(
                "DLO-RESOURCE-LATE",
                "2026-07-15T02:20:00Z",
                "2026-07-15T02:40:00Z",
            )
        ]
    )

    result = allocate_downlinks_greedily(
        catalog=catalog,
        acquisitions=acquisitions,
        downlink_set=downlink_set,
        memory_reserve_ratio=0.0,
        require_full_downlink=True,
        allow_simultaneous_imaging_downlink=False,
    )

    assert not result.feasible
    assert result.summaries[0].peak_memory_usage_mb == pytest.approx(1200.0)
    assert any("przekroczono" in reason for reason in result.rejection_reasons)


def test_downlink_capacity_reserve_is_preserved_in_schedule_entry() -> None:
    catalog = _small_catalog()
    acquisition = _acquisition("OPP-RESOURCE-A", "2026-07-15T01:10:00Z")
    downlink_set = _set(
        [
            _window(
                "DLO-RESOURCE-A",
                "2026-07-15T01:20:00Z",
                "2026-07-15T01:30:00Z",
            )
        ]
    )

    result = allocate_downlinks_greedily(
        catalog=catalog,
        acquisitions=[acquisition],
        downlink_set=downlink_set,
        memory_reserve_ratio=0.0,
        require_full_downlink=False,
        allow_simultaneous_imaging_downlink=False,
        downlink_capacity_reserve_ratio=0.25,
    )

    entry = result.downlink_entries[0]
    assert entry.planning_capacity_mb == pytest.approx(entry.capacity_mb * 0.75)
