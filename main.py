from pathlib import Path

from app.catalog_loader import load_system_catalog


def main() -> None:
    """Uruchamia podstawową walidację katalogu systemu."""

    project_directory = Path(__file__).resolve().parent
    catalog_path = (
        project_directory
        / "data"
        / "example_system.json"
    )

    catalog = load_system_catalog(catalog_path)

    sar_count = catalog.constellation_counts.get(
        "CONST-SAR",
        0,
    )
    eo_count = catalog.constellation_counts.get(
        "CONST-EO",
        0,
    )

    print("Satellite Acquisition Planner")
    print(f"Katalog: {catalog.name}")
    print(f"Wersja: {catalog.version}")
    print(f"Orbity: {len(catalog.orbits)}")
    print(f"Sensory: {len(catalog.sensors)}")
    print(f"Tryby obrazowania: {len(catalog.imaging_modes)}")
    print(f"Satelity: {len(catalog.satellites)}")
    print(f"  SAR: {sar_count}")
    print(f"  EO: {eo_count}")
    print("Katalog został wczytany i zwalidowany poprawnie.")


if __name__ == "__main__":
    main()