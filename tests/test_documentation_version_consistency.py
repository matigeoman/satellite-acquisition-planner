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
