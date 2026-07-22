from pathlib import Path

import pytest
from pydantic import ValidationError

from app.io import load_downlink_opportunity_set, load_system_catalog
from app.models.downlink import DownlinkOpportunity
from app.models.downlink_set import DownlinkOpportunitySet
from app.models.ground_station import GroundStation
from app.models.schedule import (
    DownlinkScheduleEntry,
    SatelliteResourceSummary,
    Schedule,
)
from tests.test_schedule import valid_schedule_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIRECTORY = PROJECT_ROOT / "data" / "scenarios" / "example"


def test_ground_station_coordinates_are_validated() -> None:
    station = GroundStation(
        ground_station_id="GS-TEST",
        name="Testowa stacja",
        latitude_deg=52.0,
        longitude_deg=21.0,
        max_simultaneous_contacts=2,
    )

    assert station.max_simultaneous_contacts == 2

    with pytest.raises(ValidationError):
        GroundStation(
            ground_station_id="GS-POLE",
            name="Biegun",
            latitude_deg=90.0,
            longitude_deg=10.0,
        )


def test_downlink_capacity_uses_effective_contact_duration() -> None:
    opportunity = DownlinkOpportunity(
        downlink_opportunity_id="DLO-TEST-001",
        satellite_id="SAR-01",
        ground_station_id="GS-TEST",
        start_utc="2026-07-15T01:00:00Z",
        end_utc="2026-07-15T01:10:00Z",
        data_rate_mbps=800.0,
        link_efficiency=0.75,
        setup_time_s=20.0,
        teardown_time_s=20.0,
    )

    assert opportunity.effective_duration_s == pytest.approx(560.0)
    assert opportunity.capacity_mb == pytest.approx(42_000.0)


def test_example_downlink_set_matches_catalog_and_horizon() -> None:
    catalog = load_system_catalog(EXAMPLE_DIRECTORY / "system.json")
    downlink_set = load_downlink_opportunity_set(
        EXAMPLE_DIRECTORY / "downlinks.json",
        catalog=catalog,
    )

    assert downlink_set.downlink_set_id == "DLOSET-EXAMPLE"
    assert len(downlink_set.feasible_opportunities) == 36
    assert len(catalog.ground_stations) == 2


def test_downlink_set_rejects_unknown_satellite() -> None:
    catalog = load_system_catalog(EXAMPLE_DIRECTORY / "system.json")
    source = load_downlink_opportunity_set(EXAMPLE_DIRECTORY / "downlinks.json")
    data = source.model_dump(mode="json")
    data["opportunities"][0]["satellite_id"] = "SAR-99"
    invalid = DownlinkOpportunitySet.model_validate(data)

    with pytest.raises(ValueError, match="Nieznany satelita"):
        invalid.validate_against(catalog)


def _downlink_entry_data(
    *,
    suffix: str,
    satellite_id: str,
    start: str,
    end: str,
    station_capacity: int = 1,
) -> dict:
    return {
        "entry_id": f"DOWNLINK-ENTRY-{suffix}",
        "downlink_opportunity_id": f"DLO-{suffix}",
        "satellite_id": satellite_id,
        "ground_station_id": "GS-TEST",
        "start_utc": start,
        "end_utc": end,
        "planned_data_volume_mb": 100.0,
        "capacity_mb": 200.0,
        "planning_capacity_mb": 180.0,
        "data_rate_mbps": 10.0,
        "station_capacity": station_capacity,
        "delivered_reference_ids": [f"OPP-{suffix}"],
    }


def test_schedule_allows_two_station_contacts_when_two_channels_exist() -> None:
    data = valid_schedule_data()
    data["downlink_entries"] = [
        _downlink_entry_data(
            suffix="A",
            satellite_id="SAR-01",
            start="2026-07-15T10:00:00Z",
            end="2026-07-15T10:10:00Z",
            station_capacity=2,
        ),
        _downlink_entry_data(
            suffix="B",
            satellite_id="EO-01",
            start="2026-07-15T10:05:00Z",
            end="2026-07-15T10:15:00Z",
            station_capacity=2,
        ),
    ]

    schedule = Schedule.model_validate(data)

    assert schedule.selected_downlink_windows == 2
    assert schedule.total_downlinked_data_mb == pytest.approx(200.0)


def test_schedule_rejects_station_capacity_violation() -> None:
    data = valid_schedule_data()
    data["downlink_entries"] = [
        _downlink_entry_data(
            suffix="A",
            satellite_id="SAR-01",
            start="2026-07-15T10:00:00Z",
            end="2026-07-15T10:10:00Z",
        ),
        _downlink_entry_data(
            suffix="B",
            satellite_id="EO-01",
            start="2026-07-15T10:05:00Z",
            end="2026-07-15T10:15:00Z",
        ),
    ]

    with pytest.raises(ValidationError, match="Przekroczono liczbę kanałów"):
        Schedule.model_validate(data)


def test_downlink_entry_rejects_reserved_capacity_violation() -> None:
    data = _downlink_entry_data(
        suffix="A",
        satellite_id="SAR-01",
        start="2026-07-15T10:00:00Z",
        end="2026-07-15T10:10:00Z",
    )
    data["planned_data_volume_mb"] = 190.0

    with pytest.raises(ValidationError):
        DownlinkScheduleEntry.model_validate(data)


def test_resource_summary_validates_memory_balance_and_status_flags() -> None:
    summary = SatelliteResourceSummary(
        satellite_id="SAR-01",
        memory_capacity_mb=1000.0,
        planning_memory_limit_mb=900.0,
        initial_memory_usage_mb=100.0,
        peak_memory_usage_mb=700.0,
        final_memory_usage_mb=0.0005,
        acquired_data_mb=600.0005,
        downlinked_data_mb=700.0,
        selected_downlink_windows=2,
        memory_feasible=True,
        delivery_complete=True,
    )

    assert summary.delivery_complete

    invalid = summary.model_dump()
    invalid["memory_feasible"] = False
    with pytest.raises(ValidationError, match="memory_feasible"):
        SatelliteResourceSummary.model_validate(invalid)

    invalid = summary.model_dump()
    invalid["downlinked_data_mb"] = 800.0
    with pytest.raises(ValidationError, match="przekracza dostępne dane"):
        SatelliteResourceSummary.model_validate(invalid)
