from _bootstrap import PROJECT_PATHS


from app.io import load_system_catalog
from app.scenarios.stress import (
    build_stress_scenario,
    save_stress_scenario,
)


BASE_CATALOG_PATH = PROJECT_PATHS.scenario("EXAMPLE").catalog

OUTPUT_DIRECTORY = PROJECT_PATHS.scenario_directory("STRESS")


def main() -> None:
    base_catalog = load_system_catalog(BASE_CATALOG_PATH)

    (
        stress_catalog,
        stress_request_set,
        stress_opportunity_set,
    ) = build_stress_scenario(base_catalog)

    paths = save_stress_scenario(
        catalog=stress_catalog,
        request_set=stress_request_set,
        opportunity_set=stress_opportunity_set,
        output_directory=OUTPUT_DIRECTORY,
    )

    print("SCENARIUSZ STRESOWY")
    print()
    print(f"Zlecenia: {len(stress_request_set.requests)}")
    print(f"Obowiązkowe: {len(stress_request_set.mandatory_requests)}")
    print(f"Tryby: {stress_request_set.request_mode_counts}")
    print(f"Okazje: {len(stress_opportunity_set.opportunities)}")
    print(f"Wykonalne: {len(stress_opportunity_set.feasible_opportunities)}")
    print(f"Typy sensorów: {stress_opportunity_set.sensor_type_counts}")
    print()

    print("OGRANICZENIA SATELITÓW")

    for satellite in stress_catalog.satellites:
        print(
            f"  {satellite.satellite_id}: "
            f"pamięć {satellite.memory_capacity_mb:.0f} MB, "
            f"akwizycje {satellite.max_acquisitions_per_day}, "
            f"czas {satellite.max_imaging_time_per_day_s:.0f} s"
        )

    print()
    print("ZAPISANE PLIKI")

    for name, path in paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
