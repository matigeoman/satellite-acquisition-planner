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
