from app.config.paths import DEFAULT_PATHS
from app.io import load_schedule
from app.services.scenario_service import ScenarioService


def main() -> None:
    """Wczytuje i podsumowuje przykładowy scenariusz projektu."""

    paths = DEFAULT_PATHS
    scenario = ScenarioService(project_root=paths.root).load("EXAMPLE")
    catalog = scenario.catalog
    request_set = scenario.request_set
    opportunity_set = scenario.opportunity_set
    schedule_path = paths.reference_schedule(
        scenario_id="EXAMPLE",
        algorithm_value="GREEDY",
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
    print()

    print("ZLECENIA")
    print(f"Zbiór: {request_set.name}")
    print(f"Wszystkie: {len(request_set.requests)}")
    print(f"Aktywne: {len(request_set.active_requests)}")
    print(f"Obowiązkowe: {len(request_set.mandatory_requests)}")
    print(f"Tryby zleceń: {request_set.request_mode_counts}")
    print(f"Typy geometrii: {request_set.geometry_type_counts}")
    print()

    print("OKAZJE AKWIZYCYJNE")
    print(f"Zbiór: {opportunity_set.name}")
    print(f"Wszystkie: {len(opportunity_set.opportunities)}")
    print(f"Wykonalne: {len(opportunity_set.feasible_opportunities)}")
    print(f"Niewykonalne: {len(opportunity_set.infeasible_opportunities)}")
    print(f"Typy sensorów: {opportunity_set.sensor_type_counts}")
    print()

    print("HARMONOGRAM GREEDY")
    if schedule_path.exists():
        schedule = load_schedule(schedule_path)
        print(f"Status: {schedule.status.value}")
        print(f"Akwizycje: {schedule.total_acquisitions}")
        print(f"Zaplanowane zlecenia: {len(schedule.scheduled_request_ids)}")
        print(f"Nieprzypisane zlecenia: {len(schedule.unassigned_request_ids)}")
        print(f"Rozmiar danych: {schedule.total_data_volume_mb:.3f} MB")
        print(f"Funkcja celu: {schedule.objective_value:.6f}")
    else:
        print("Harmonogram nie został jeszcze wygenerowany.")
        print(r"Uruchom: python .\scripts\run_greedy.py")

    print()
    print("Dane zostały wczytane i zwalidowane poprawnie.")


if __name__ == "__main__":
    main()
