from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = tuple(sorted(PROJECT_ROOT.rglob("*.md")))
INLINE_CODE = re.compile(r"`[^`]*`")
TEX_COMMAND = re.compile(
    r"\\(?:frac|sum|leq|leqslant|geq|geqslant|in|overline|ln|eta|quad|"
    r"text|left|right|forall|cdot|times|sqrt|mathrm|mathbf|mathbb)\b"
)
CANONICAL_GREEDY_TERMS = (
    r"\frac{w_s}{n_i}",
    r"- w_d \tau_i",
    r"- w_m D_i",
    r"\overline{U_i^{\mathrm{blocked}}}",
    r"\ln(1+|B_i|)",
)
GREEDY_DOCUMENTS = (
    PROJECT_ROOT / "docs" / "planning_model.md",
    PROJECT_ROOT / "docs" / "research_foundations.md",
)
DOWNLINK_DOCUMENTS = (
    PROJECT_ROOT / "docs" / "planning_model.md",
    PROJECT_ROOT / "docs" / "downlink_and_dynamic_memory.md",
)
CANONICAL_DOWNLINK_TERMS = (
    r"M_s(t)=M_s^0",
    r"D_i x_i",
    r"q_w",
    r"e_i",
    r"f_w",
)


def _lines_outside_fenced_code(text: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    in_fence = False

    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            result.append((line_number, line))

    return result


def test_markdown_does_not_use_unsupported_display_math_delimiters() -> None:
    failures: list[str] = []

    for path in MARKDOWN_FILES:
        for line_number, line in _lines_outside_fenced_code(
            path.read_text(encoding="utf-8")
        ):
            if line.strip() in {r"\[", r"\]"}:
                failures.append(f"{path.relative_to(PROJECT_ROOT)}:{line_number}")

    assert not failures, (
        r"Use standalone $$ delimiters for display math instead of \[ or \]: "
        + ", ".join(failures)
    )


def test_markdown_display_math_blocks_are_balanced_and_standalone() -> None:
    failures: list[str] = []

    for path in MARKDOWN_FILES:
        delimiters: list[int] = []
        for line_number, line in _lines_outside_fenced_code(
            path.read_text(encoding="utf-8")
        ):
            visible_line = INLINE_CODE.sub("", line)
            if "$$" not in visible_line:
                continue
            if visible_line.strip() != "$$":
                failures.append(
                    f"{path.relative_to(PROJECT_ROOT)}:{line_number}: "
                    "display delimiter must be on its own line"
                )
                continue
            delimiters.append(line_number)

        if len(delimiters) % 2 != 0:
            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}: unbalanced $$ at {delimiters}"
            )

    assert not failures, "; ".join(failures)


def test_tex_commands_are_inside_math_blocks_or_inline_math() -> None:
    failures: list[str] = []

    for path in MARKDOWN_FILES:
        in_math = False
        for line_number, line in _lines_outside_fenced_code(
            path.read_text(encoding="utf-8")
        ):
            if line.strip() == "$$":
                in_math = not in_math
                continue
            if TEX_COMMAND.search(line) and not in_math and "$" not in line:
                failures.append(f"{path.relative_to(PROJECT_ROOT)}:{line_number}")

    assert not failures, (
        "TeX command outside a math block or inline math: " + ", ".join(failures)
    )


def test_markdown_does_not_use_unsupported_katex_macros() -> None:
    failures: list[str] = []

    for path in MARKDOWN_FILES:
        text = path.read_text(encoding="utf-8")
        if r"\operatorname" in text:
            failures.append(str(path.relative_to(PROJECT_ROOT)))

    assert not failures, (
        r"Use KaTeX-safe notation such as \mathrm instead of \operatorname: "
        + ", ".join(failures)
    )


def test_greedy_heuristic_uses_canonical_notation() -> None:
    failures: list[str] = []

    for path in GREEDY_DOCUMENTS:
        text = path.read_text(encoding="utf-8")
        missing = [term for term in CANONICAL_GREEDY_TERMS if term not in text]
        if missing:
            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}: missing {', '.join(missing)}"
            )

        forbidden = (
            r"\overline{U(N_i)}",
            r"- w_d d_i",
            r"- w_m m_i",
        )
        present = [term for term in forbidden if term in text]
        if present:
            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}: forbidden {', '.join(present)}"
            )

    assert not failures, "; ".join(failures)


def test_downlink_model_uses_canonical_notation() -> None:
    failures: list[str] = []

    for path in DOWNLINK_DOCUMENTS:
        text = path.read_text(encoding="utf-8")
        missing = [term for term in CANONICAL_DOWNLINK_TERMS if term not in text]
        if missing:
            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}: missing {', '.join(missing)}"
            )

        forbidden = (
            r"D_a x_a",
            r"d_w",
            r"t_a^{end}",
            r"t_w^{end}",
            "`d_i` oznacza objętość danych akwizycji",
        )
        present = [term for term in forbidden if term in text]
        if present:
            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}: forbidden {', '.join(present)}"
            )

    assert not failures, "; ".join(failures)


def test_planning_model_does_not_reuse_duration_symbol_for_data_volume() -> None:
    path = PROJECT_ROOT / "docs" / "planning_model.md"
    text = path.read_text(encoding="utf-8")

    assert "`d_i` — czas akwizycji" not in text
    assert "`d_i` oznacza objętość danych akwizycji" not in text
    assert "`τ_i` — czas trwania akwizycji" in text
    assert "`D_i` — objętość danych akwizycji" in text
