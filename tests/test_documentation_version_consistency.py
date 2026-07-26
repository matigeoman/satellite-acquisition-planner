from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_VERSION = ".".join(("1", "3", "0"))

CURRENT_DOCUMENTATION = (
    "README.md",
    "docs/benchmarking.md",
    "docs/downlink_and_dynamic_memory.md",
    "docs/index.md",
    "docs/planning_model.md",
    "docs/references.md",
    "docs/research_foundations.md",
    "docs/scientific_methodology.md",
)


def test_current_documentation_has_no_legacy_version_markers() -> None:
    failures: list[str] = []

    for relative_path in CURRENT_DOCUMENTATION:
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

        if LEGACY_VERSION in text:
            failures.append(relative_path)

    assert not failures, (
        "Legacy version references remain in current documentation: "
        + ", ".join(failures)
    )


def test_documentation_index_matches_application_version() -> None:
    version = (PROJECT_ROOT / "VERSION").read_text(
        encoding="utf-8"
    ).strip()
    index = (PROJECT_ROOT / "docs/index.md").read_text(
        encoding="utf-8"
    )

    assert f"Wersja dokumentacji: `{version}`." in index



def test_greedy_2_formula_matches_implementation() -> None:
    planning_model = (
        PROJECT_ROOT / "docs/planning_model.md"
    ).read_text(encoding="utf-8")

    assert r"\ln(1+r_i)" in planning_model
    assert (
        r"\overline{U_i^{\mathrm{blocked}}}"
        in planning_model
    )
    assert r"\overline{U(N_i)}," not in planning_model


def test_unreleased_contains_only_post_140_work() -> None:
    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text(
        encoding="utf-8"
    )
    unreleased = changelog.split(
        "## [Unreleased]", 1
    )[1].split("## [1.4.0]", 1)[0]

    assert "najnowszej epoce OMM" not in unreleased
    assert "`GitPython` z `3.1.55` do `3.1.57`" in unreleased
    assert "ln(1 + r_i)" in unreleased


def test_manual_docker_build_pulls_base_image() -> None:
    release_notes = (
        PROJECT_ROOT / "RELEASE_NOTES.md"
    ).read_text(encoding="utf-8")

    assert (
        "docker compose build --pull --no-cache satplan"
        in release_notes
    )
