from app.models.enums import PlanningAlgorithm
from app.ui.pages.public_planning import build_public_schedule_id


def test_public_cp_sat_schedule_id_uses_hyphen_not_underscore() -> None:
    assert (
        build_public_schedule_id(PlanningAlgorithm.CP_SAT) == "SCHEDULE-PUBLIC-CP-SAT"
    )


def test_public_greedy_schedule_id_remains_valid() -> None:
    assert (
        build_public_schedule_id(PlanningAlgorithm.GREEDY) == "SCHEDULE-PUBLIC-GREEDY"
    )
