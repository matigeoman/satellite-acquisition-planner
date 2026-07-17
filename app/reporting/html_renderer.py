from __future__ import annotations

import base64
import html
from typing import Any

from app.reporting.models import ScientificReportSnapshot


def _display(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _table(rows: tuple[dict[str, Any], ...], *, max_rows: int = 100) -> str:
    if not rows:
        return '<p class="empty">Brak danych.</p>'
    columns = list(rows[0])
    head = "".join(f"<th>{html.escape(str(column))}</th>" for column in columns)
    body_rows = []
    for row in rows[:max_rows]:
        cells = "".join(
            f"<td>{html.escape(_display(row.get(column)))}</td>"
            for column in columns
        )
        body_rows.append(f"<tr>{cells}</tr>")
    note = ""
    if len(rows) > max_rows:
        note = (
            f'<p class="note">Tabela skrócona: pokazano {max_rows} z '
            f"{len(rows)} wierszy. Pełne dane znajdują się w results.xlsx i CSV.</p>"
        )
    return (
        '<div class="table-scroll"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table></div>"
        + note
    )


def _figure(name: str, figures: dict[str, bytes], caption: str) -> str:
    raw = figures.get(name)
    if raw is None:
        return ""
    encoded = base64.b64encode(raw).decode("ascii")
    return (
        '<figure><img src="data:image/png;base64,'
        + encoded
        + f'" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    )


def render_html(
    snapshot: ScientificReportSnapshot,
    figures: dict[str, bytes],
) -> bytes:
    metrics = "".join(
        '<div class="metric"><span class="metric-label">'
        + html.escape(str(item["metric"]))
        + '</span><strong class="metric-value">'
        + html.escape(_display(item["value"]))
        + " "
        + html.escape(str(item.get("unit", "")))
        + "</strong></div>"
        for item in snapshot.overview_metrics
    )
    warnings = "".join(
        f"<li>{html.escape(warning)}</li>" for warning in snapshot.warnings
    )
    limitations = "".join(
        f"<li>{html.escape(item)}</li>" for item in snapshot.limitations
    )


    methodology_section = ""
    if snapshot.include_methodology:
        methodology_section = (
            "<h2>2. Metodyka</h2><p>"
            + html.escape(snapshot.narrative["methodology"])
            + "</p>"
        )

    stk_section = ""
    if snapshot.include_stk_validation:
        stk_section = (
            "<h2>7. Walidacja względem STK</h2><p>"
            + html.escape(snapshot.narrative["validation"])
            + "</p>"
            + _figure(
                "stk_access_errors.png",
                figures,
                "Rysunek 4. Średnie błędy bezwzględne okien względem STK.",
            )
            + _table(snapshot.stk_access_rows)
            + "<h3>7.1. Próbki AER</h3>"
            + _table(snapshot.stk_aer_rows)
        )

    benchmark_section = ""
    if snapshot.include_benchmarks:
        benchmark_section = (
            "<h2>8. Benchmark Greedy i CP-SAT</h2><p>"
            + html.escape(snapshot.narrative["benchmark"])
            + "</p>"
            + _figure(
                "benchmark_objective.png",
                figures,
                "Rysunek 5. Średnia wartość funkcji celu w benchmarku.",
            )
            + _figure(
                "benchmark_runtime.png",
                figures,
                "Rysunek 6. Średni czas obliczeń w benchmarku.",
            )
            + _table(snapshot.benchmark_summary_rows)
        )

    limitations_section = ""
    if snapshot.include_limitations:
        limitations_section = (
            "<h2>10. Ograniczenia i interpretacja</h2><p>"
            + html.escape(snapshot.narrative["interpretation"])
            + "</p><ul>"
            + limitations
            + "</ul>"
        )

    document = f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(snapshot.title)}</title>
<style>
:root {{ color-scheme: light; --ink:#172033; --muted:#5f6b7a; --line:#d8dee8; --panel:#f5f7fa; --accent:#1f5f99; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:#eef2f6; color:var(--ink); font-family:Arial,Helvetica,sans-serif; line-height:1.45; }}
main {{ max-width:1180px; margin:28px auto; background:white; padding:46px 54px 64px; box-shadow:0 8px 34px rgba(20,35,55,.10); }}
h1 {{ font-size:32px; margin:0 0 8px; }}
h2 {{ margin-top:42px; padding-bottom:8px; border-bottom:2px solid var(--accent); }}
h3 {{ margin-top:28px; }}
.meta {{ color:var(--muted); margin-bottom:28px; }}
.lead {{ font-size:17px; }}
.metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin:22px 0; }}
.metric {{ border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:13px 15px; }}
.metric-label {{ display:block; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
.metric-value {{ display:block; font-size:21px; margin-top:4px; }}
.table-scroll {{ overflow:auto; border:1px solid var(--line); border-radius:7px; }}
table {{ border-collapse:collapse; width:100%; font-size:12px; }}
th,td {{ padding:8px 9px; border-bottom:1px solid var(--line); vertical-align:top; text-align:left; white-space:nowrap; }}
th {{ background:#eaf0f6; position:sticky; top:0; }}
figure {{ margin:26px auto; text-align:center; }}
figure img {{ max-width:100%; height:auto; }}
figcaption {{ color:var(--muted); font-size:13px; margin-top:8px; }}
.note,.empty {{ color:var(--muted); font-style:italic; }}
.warning {{ border-left:4px solid #a16800; background:#fff7e6; padding:12px 18px; }}
footer {{ margin-top:52px; border-top:1px solid var(--line); padding-top:16px; color:var(--muted); font-size:12px; }}
@media print {{ body {{ background:white; }} main {{ box-shadow:none; margin:0; max-width:none; padding:18mm; }} .table-scroll {{ overflow:visible; }} th {{ position:static; }} }}
</style>
</head>
<body><main>
<header>
<h1>{html.escape(snapshot.title)}</h1>
<div class="meta">Projekt: {html.escape(snapshot.project_name)} · ID: {html.escape(snapshot.project_id)}<br>
Autor: {html.escape(snapshot.author or "nie podano")} · {html.escape(snapshot.institution or "")}
<br>Wygenerowano UTC: {snapshot.generated_at_utc.isoformat()} · SatPlan {html.escape(snapshot.application_version)}</div>
<p class="lead">{html.escape(snapshot.description or snapshot.narrative["results"])}</p>
</header>
<h2>1. Podsumowanie</h2>
<div class="metrics">{metrics}</div>
<p>{html.escape(snapshot.narrative["results"])}</p>
{('<div class="warning"><strong>Uwagi kompletności</strong><ul>' + warnings + '</ul></div>') if warnings else ''}
{methodology_section}
<h2>3. System satelitarny</h2>
{_table(snapshot.satellite_rows)}
<h2>4. Zlecenia obserwacyjne</h2>
{_table(snapshot.request_rows)}
<h2>5. Okna dostępu i okazje</h2>
<h3>5.1. Okna dostępu</h3>
{_table(snapshot.access_rows, max_rows=60)}
<h3>5.2. Okazje akwizycyjne</h3>
{_table(snapshot.opportunity_rows, max_rows=60)}
<h2>6. Harmonogram</h2>
<p>{html.escape(snapshot.narrative["results"])}</p>
{_figure("schedule_sensor_mix.png", figures, "Rysunek 1. Struktura harmonogramu według typu sensora.")}
{_figure("schedule_satellite_load.png", figures, "Rysunek 2. Liczba akwizycji przypisana do satelitów.")}
{_table(snapshot.schedule_rows, max_rows=100)}
<h3>6.1. Diagnostyka zleceń</h3>
{_figure("unassigned_reasons.png", figures, "Rysunek 3. Przyczyny braku pełnej realizacji zleceń.")}
{_table(snapshot.request_diagnostic_rows, max_rows=100)}
<h3>6.2. Wykorzystanie satelitów</h3>
{_table(snapshot.satellite_kpi_rows)}
{stk_section}
{benchmark_section}
<h2>9. Historia harmonogramów</h2>
{_table(snapshot.schedule_history_rows)}
{limitations_section}
<footer>Raport wygenerowany automatycznie przez Satellite Acquisition Planner. Tabele pełne znajdują się w plikach CSV i results.xlsx.</footer>
</main></body></html>"""
    return document.encode("utf-8")
