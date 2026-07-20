"""Import raportów STK, porównanie okien i przygotowanie przypadków walidacji."""

from app.integrations.stk_validation.comparison import (
    compare_access_intervals,
    compare_aer_samples,
)
from app.integrations.stk_validation.export import build_stk_validation_bundle
from app.integrations.stk_validation.models import (
    AccessValidationResult,
    AerValidationResult,
    ErrorStatistics,
    MatchedAccessInterval,
    MatchedAerSample,
    ParsedStkAccessReport,
    ParsedStkAerReport,
    StkAccessInterval,
    StkAerSample,
)
from app.integrations.stk_validation.parser import (
    parse_stk_access_report,
    parse_stk_aer_report,
)

__all__ = [
    "AccessValidationResult",
    "AerValidationResult",
    "ErrorStatistics",
    "MatchedAccessInterval",
    "MatchedAerSample",
    "ParsedStkAccessReport",
    "ParsedStkAerReport",
    "StkAccessInterval",
    "StkAerSample",
    "build_stk_validation_bundle",
    "compare_access_intervals",
    "compare_aer_samples",
    "parse_stk_access_report",
    "parse_stk_aer_report",
]
