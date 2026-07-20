from _bootstrap import PROJECT_PATHS


from app.analysis.schedule_report import (
    analyze_schedule,
    export_schedule_analysis,
)
from app.io import load_system_catalog
from app.io import load_opportunity_set
from app.io import load_request_set
from app.io import load_schedule


CATALOG_PATH = PROJECT_PATHS.scenario("EXAMPLE").catalog

REQUEST_SET_PATH = PROJECT_PATHS.scenario("EXAMPLE").requests

OPPORTUNITY_SET_PATH = PROJECT_PATHS.scenario("EXAMPLE").opportunities

SCHEDULE_PATH = PROJECT_PATHS.reference_schedule(
    scenario_id="EXAMPLE", algorithm_value="GREEDY"
)

REPORT_DIRECTORY = PROJECT_PATHS.reports


def main() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    request_set = load_request_set(REQUEST_SET_PATH)

    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH,
        catalog=catalog,
        request_set=request_set,
    )

    schedule = load_schedule(SCHEDULE_PATH)

    analysis = analyze_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        schedule=schedule,
    )

    exported_paths = export_schedule_analysis(
        analysis,
        REPORT_DIRECTORY,
        prefix="greedy",
    )

    print("ANALIZA HARMONOGRAMU GREEDY")
    print()

    print("REALIZACJA ZLECEŃ")
    print(f"Wszystkie aktywne: {analysis.total_active_requests}")
    print(f"W pełni zrealizowane: {analysis.fully_satisfied_requests}")
    print(f"Częściowo zrealizowane: {analysis.partially_satisfied_requests}")
    print(f"Nieprzypisane: {analysis.unassigned_requests}")
    print(f"Poziom realizacji: {analysis.satisfaction_ratio:.2%}")
    print(f"Realizacja obowiązkowych: {analysis.mandatory_satisfaction_ratio:.2%}")
    print()

    print("AKWIZYCJE")
    print(f"Wszystkie: {analysis.total_acquisitions}")
    print(f"SAR: {analysis.sar_acquisitions}")
    print(f"Optyczne: {analysis.optical_acquisitions}")
    print(f"Średnia jakość: {analysis.average_selected_quality:.4f}")
    print(f"Średnie pokrycie: {analysis.average_selected_coverage:.4f}")
    print(f"Funkcja celu: {analysis.objective_value:.4f}")
    print()

    print("PRZYCZYNY BRAKU REALIZACJI")

    if analysis.unassigned_reason_counts:
        for reason, count in analysis.unassigned_reason_counts.items():
            print(f"  {reason}: {count}")
    else:
        print("  Wszystkie zlecenia zostały zrealizowane.")

    print()
    print("WYKORZYSTANIE SATELITÓW")

    for satellite in analysis.satellite_kpis:
        print(
            f"  {satellite.satellite_id}: "
            f"{satellite.scheduled_acquisitions} akwizycji, "
            f"czas {satellite.imaging_time_s:.1f} s, "
            f"dane {satellite.generated_data_mb:.1f} MB"
        )

    print()
    print("RAPORTY CSV")

    for report_name, path in exported_paths.items():
        print(f"  {report_name}: {path}")


if __name__ == "__main__":
    main()
