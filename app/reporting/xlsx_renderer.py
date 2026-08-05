from __future__ import annotations

import io

import xlsxwriter

from app.reporting.models import ScientificReportSnapshot


_SHEET_NAMES = {
    "satellites": "Satelity",
    "requests": "Zlecenia",
    "access_windows": "Okna_dostepu",
    "opportunities": "Okazje",
    "schedule_entries": "Harmonogram",
    "request_diagnostics": "Diagnostyka",
    "satellite_kpis": "KPI_satelitow",
    "benchmark_runs": "Benchmark_runs",
    "benchmark_summary": "Benchmark_summary",
    "schedule_history_summary": "Historia_planow",
    "schedule_history": "Historia_szczegoly",
    "stk_access_matches": "STK_Access",
    "stk_aer_matches": "STK_AER",
}


def _write_table(
    worksheet,
    rows,
    header_format,
    percent_format,
    wrapped_format,
    *,
    wrap_long_text: bool = False,
) -> None:
    if not rows:
        worksheet.write(0, 0, "Brak danych")
        worksheet.set_column(0, 0, 24)
        return
    columns = list(rows[0])
    for column_index, column in enumerate(columns):
        worksheet.write(0, column_index, column, header_format)
    widths = [len(str(column)) for column in columns]
    for row_index, row in enumerate(rows, start=1):
        for column_index, column in enumerate(columns):
            value = row.get(column)
            cell_format = None
            if isinstance(value, bool):
                value = "Tak" if value else "Nie"
            if isinstance(value, (int, float)) and "ratio" in column.lower():
                cell_format = percent_format
            elif wrap_long_text and isinstance(value, str) and len(value) > 80:
                cell_format = wrapped_format
            worksheet.write(row_index, column_index, value, cell_format)
            widths[column_index] = min(
                45,
                max(widths[column_index], len(str(value)) if value is not None else 1),
            )
    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, len(rows), len(columns) - 1)
    for index, width in enumerate(widths):
        worksheet.set_column(index, index, max(10, min(width + 2, 45)))


def render_xlsx(snapshot: ScientificReportSnapshot) -> bytes:
    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
    header = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#D9E6F2",
            "border": 1,
            "text_wrap": True,
            "valign": "top",
        }
    )
    title = workbook.add_format(
        {"bold": True, "font_size": 18, "font_color": "#1F4E78"}
    )
    subtitle = workbook.add_format(
        {"bold": True, "font_size": 11, "font_color": "#44546A"}
    )
    metric_label = workbook.add_format(
        {"bold": True, "bg_color": "#EAF0F6", "border": 1}
    )
    metric_value = workbook.add_format({"border": 1})
    percent = workbook.add_format({"num_format": "0.00%"})
    wrapped = workbook.add_format({"text_wrap": True, "valign": "top"})

    overview = workbook.add_worksheet("Podsumowanie")
    overview.hide_gridlines(2)
    overview.write(0, 0, snapshot.title, title)
    overview.write(1, 0, snapshot.project_name, subtitle)
    overview.write(3, 0, "ID projektu", metric_label)
    overview.write(3, 1, snapshot.project_id, metric_value)
    overview.write(4, 0, "Autor", metric_label)
    overview.write(4, 1, snapshot.author or "nie podano", metric_value)
    overview.write(5, 0, "Instytucja", metric_label)
    overview.write(5, 1, snapshot.institution or "nie podano", metric_value)
    overview.write(6, 0, "Wygenerowano UTC", metric_label)
    overview.write(6, 1, snapshot.generated_at_utc.isoformat(), metric_value)
    overview.write(8, 0, "Metryka", header)
    overview.write(8, 1, "Wartość", header)
    overview.write(8, 2, "Jednostka", header)
    for index, item in enumerate(snapshot.overview_metrics, start=10):
        overview.write(index - 1, 0, item["metric"], metric_label)
        overview.write(index - 1, 1, item["value"], metric_value)
        overview.write(index - 1, 2, item.get("unit", ""), metric_value)
    overview.set_column(0, 0, 34)
    overview.set_column(1, 1, 24)
    overview.set_column(2, 2, 12)

    for key, rows in snapshot.table_map().items():
        worksheet = workbook.add_worksheet(_SHEET_NAMES[key])
        _write_table(
            worksheet,
            rows,
            header,
            percent,
            wrapped,
            wrap_long_text=key == "schedule_history",
        )
        if key == "schedule_history":
            worksheet.hide()

    if snapshot.benchmark_summary_rows:
        sheet = workbook.get_worksheet_by_name("Benchmark_summary")
        if sheet is None:
            raise RuntimeError(
                "Benchmark summary worksheet was not created."
            )

        columns = list(snapshot.benchmark_summary_rows[0])
        if "request_count" in columns and "objective_mean" in columns:
            request_col = columns.index("request_count")
            objective_col = columns.index("objective_mean")
            chart = workbook.add_chart({"type": "line"})
            if chart is None:
                raise RuntimeError(
                    "Benchmark chart could not be created."
                )

            chart.add_series(
                {
                    "name": "Średnia funkcja celu",
                    "categories": [
                        "Benchmark_summary",
                        1,
                        request_col,
                        len(snapshot.benchmark_summary_rows),
                        request_col,
                    ],
                    "values": [
                        "Benchmark_summary",
                        1,
                        objective_col,
                        len(snapshot.benchmark_summary_rows),
                        objective_col,
                    ],
                    "marker": {"type": "circle"},
                }
            )
            chart.set_title({"name": "Funkcja celu w benchmarku"})
            chart.set_x_axis({"name": "Liczba zleceń"})
            chart.set_y_axis({"name": "Wartość celu"})
            sheet.insert_chart(
                1,
                16,
                chart,
                {
                    "x_scale": 1.25,
                    "y_scale": 1.1,
                },
            )

    workbook.close()
    return buffer.getvalue()
