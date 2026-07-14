from pathlib import Path

from app.catalog_loader import load_system_catalog
from app.opportunity_loader import load_opportunity_set
from app.request_loader import load_request_set
from app.schedule_loader import load_schedule


def main() -> None:
    """Wczytuje i waliduje dane wejściowe oraz harmonogram."""

    project_directory = Path(__file__).resolve().parent

    catalog_path = (
        project_directory
        / "data"
        / "example_system.json"
    )

    requests_path = (
        project_directory
        / "data"
        / "example_requests.json"
    )

    opportunities_path = (
        project_directory
        / "data"
        / "example_opportunities.json"
    )

    schedule_path = (
        project_directory
        / "data"
        / "example_schedule_greedy.json"
    )

    catalog = load_system_catalog(
        catalog_path
    )

    request_set = load_request_set(
        requests_path
    )

    opportunity_set = load_opportunity_set(
        opportunities_path,
        catalog=catalog,
        request_set=request_set,
    )

    sar_satellite_count = catalog.constellation_counts.get(
        "CONST-SAR",
        0,
    )

    eo_satellite_count = catalog.constellation_counts.get(
        "CONST-EO",
        0,
    )

    print("Satellite Acquisition Planner")
    print()

    print("SYSTEM")
    print(f"Katalog: {catalog.name}")
    print(f"Wersja: {catalog.version}")
    print(f"Orbity: {len(catalog.orbits)}")
    print(f"Sensory: {len(catalog.sensors)}")
    print(f"Tryby obrazowania: {len(catalog.imaging_modes)}")
    print(f"Satelity: {len(catalog.satellites)}")
    print(f"  SAR: {sar_satellite_count}")
    print(f"  EO: {eo_satellite_count}")
    print()

    print("ZLECENIA")
    print(f"Zbiór: {request_set.name}")
    print(f"Wszystkie: {len(request_set.requests)}")
    print(f"Aktywne: {len(request_set.active_requests)}")
    print(f"Obowiązkowe: {len(request_set.mandatory_requests)}")
    print(
        f"Tryby zleceń: "
        f"{request_set.request_mode_counts}"
    )
    print(
        f"Typy geometrii: "
        f"{request_set.geometry_type_counts}"
    )
    print()

    print("OKAZJE AKWIZYCYJNE")
    print(f"Zbiór: {opportunity_set.name}")
    print(
        f"Wszystkie: "
        f"{len(opportunity_set.opportunities)}"
    )
    print(
        f"Wykonalne: "
        f"{len(opportunity_set.feasible_opportunities)}"
    )
    print(
        f"Niewykonalne: "
        f"{len(opportunity_set.infeasible_opportunities)}"
    )
    print(
        f"Typy sensorów: "
        f"{opportunity_set.sensor_type_counts}"
    )
    print()

    print("HARMONOGRAM GREEDY")

    if schedule_path.exists():
        schedule = load_schedule(
            schedule_path
        )

        print(f"Status: {schedule.status.value}")
        print(
            f"Akwizycje: "
            f"{schedule.total_acquisitions}"
        )
        print(
            f"Zaplanowane zlecenia: "
            f"{len(schedule.scheduled_request_ids)}"
        )
        print(
            f"Nieprzypisane zlecenia: "
            f"{len(schedule.unassigned_request_ids)}"
        )
        print(
            f"Rozmiar danych: "
            f"{schedule.total_data_volume_mb:.3f} MB"
        )
        print(
            f"Funkcja celu: "
            f"{schedule.objective_value:.6f}"
        )
    else:
        print(
            "Harmonogram nie został jeszcze wygenerowany."
        )
        print(
            "Uruchom: "
            "python .\\scripts\\run_greedy.py"
        )

    print()
    print("Dane zostały wczytane i zwalidowane poprawnie.")


if __name__ == "__main__":
    main()