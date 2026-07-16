from _bootstrap import PROJECT_PATHS

from app.services.scenario_service import ScenarioService


def main() -> None:
    """Sprawdza strukturę katalogów i poprawność scenariuszy wejściowych."""

    PROJECT_PATHS.ensure_output_directories()
    service = ScenarioService(project_root=PROJECT_PATHS.root)

    print("KONTROLA PROJEKTU")
    print(f"Katalog główny: {PROJECT_PATHS.root}")
    print()

    for scenario_id in service.scenario_ids:
        scenario = service.load(scenario_id)
        print(f"{scenario_id}")
        print(f"  satelity: {scenario.satellite_count}")
        print(f"  aktywne zlecenia: {scenario.active_request_count}")
        print(f"  okazje: {scenario.opportunity_count}")
        print(f"  wykonalne okazje: {scenario.feasible_opportunity_count}")

    print()
    print("Struktura i dane wejściowe są poprawne.")


if __name__ == "__main__":
    main()
