from __future__ import annotations

import inspect

from app.analysis import (
    EntryKPI,
    RequestDiagnostic,
    RequestFulfillmentStatus,
    SatelliteKPI,
    ScheduleAnalysis,
    UnassignedReasonCode,
    analyze_schedule,
    export_schedule_analysis,
)
from app.analysis.schedule import (
    EntryKPI as PackageEntryKPI,
    RequestDiagnostic as PackageRequestDiagnostic,
    RequestFulfillmentStatus as PackageRequestFulfillmentStatus,
    SatelliteKPI as PackageSatelliteKPI,
    ScheduleAnalysis as PackageScheduleAnalysis,
    UnassignedReasonCode as PackageUnassignedReasonCode,
    analyze_schedule as package_analyze_schedule,
    export_schedule_analysis as package_export_schedule_analysis,
)
from app.analysis.schedule_report import (
    EntryKPI as LegacyEntryKPI,
    RequestDiagnostic as LegacyRequestDiagnostic,
    RequestFulfillmentStatus as LegacyRequestFulfillmentStatus,
    SatelliteKPI as LegacySatelliteKPI,
    ScheduleAnalysis as LegacyScheduleAnalysis,
    UnassignedReasonCode as LegacyUnassignedReasonCode,
    analyze_schedule as legacy_analyze_schedule,
    export_schedule_analysis as legacy_export_schedule_analysis,
)
from app.services import (
    PlanningComparisonResult,
    PlanningOptions,
    PlanningResult,
    ReplanningResult,
)
from app.services.comparison_service import (
    PlanningComparisonResult as LegacyPlanningComparisonResult,
)
from app.services.contracts import (
    PlanningComparisonResult as ContractPlanningComparisonResult,
    PlanningOptions as ContractPlanningOptions,
    PlanningResult as ContractPlanningResult,
    ReplanningResult as ContractReplanningResult,
)
from app.services.planning_service import (
    PlanningOptions as LegacyPlanningOptions,
    PlanningResult as LegacyPlanningResult,
)
from app.services.replanning_service import (
    ReplanningResult as LegacyReplanningResult,
)


def test_schedule_analysis_public_imports_are_compatible() -> None:
    assert ScheduleAnalysis is PackageScheduleAnalysis
    assert ScheduleAnalysis is LegacyScheduleAnalysis
    assert RequestDiagnostic is PackageRequestDiagnostic
    assert RequestDiagnostic is LegacyRequestDiagnostic
    assert SatelliteKPI is PackageSatelliteKPI
    assert SatelliteKPI is LegacySatelliteKPI
    assert EntryKPI is PackageEntryKPI
    assert EntryKPI is LegacyEntryKPI


def test_schedule_analysis_enums_are_compatible() -> None:
    assert RequestFulfillmentStatus is PackageRequestFulfillmentStatus
    assert RequestFulfillmentStatus is LegacyRequestFulfillmentStatus
    assert UnassignedReasonCode is PackageUnassignedReasonCode
    assert UnassignedReasonCode is LegacyUnassignedReasonCode


def test_schedule_analysis_functions_are_compatible() -> None:
    assert analyze_schedule is package_analyze_schedule
    assert analyze_schedule is legacy_analyze_schedule
    assert export_schedule_analysis is package_export_schedule_analysis
    assert export_schedule_analysis is legacy_export_schedule_analysis


def test_schedule_report_is_only_compatibility_facade() -> None:
    source = inspect.getsource(
        __import__(
            "app.analysis.schedule_report",
            fromlist=["schedule_report"],
        )
    )

    assert "def analyze_schedule" not in source
    assert "def export_schedule_analysis" not in source
    assert "from app.analysis.schedule import" in source


def test_planning_contracts_keep_legacy_imports() -> None:
    assert PlanningOptions is ContractPlanningOptions
    assert PlanningOptions is LegacyPlanningOptions
    assert PlanningResult is ContractPlanningResult
    assert PlanningResult is LegacyPlanningResult


def test_replanning_contract_keeps_legacy_import() -> None:
    assert ReplanningResult is ContractReplanningResult
    assert ReplanningResult is LegacyReplanningResult


def test_comparison_contract_keeps_legacy_import() -> None:
    assert PlanningComparisonResult is ContractPlanningComparisonResult
    assert PlanningComparisonResult is LegacyPlanningComparisonResult


def test_contracts_live_outside_service_implementations() -> None:
    assert PlanningOptions.__module__ == "app.services.contracts.planning"
    assert PlanningResult.__module__ == "app.services.contracts.planning"
    assert ReplanningResult.__module__ == "app.services.contracts.replanning"
    assert (
        PlanningComparisonResult.__module__
        == "app.services.contracts.comparison"
    )
