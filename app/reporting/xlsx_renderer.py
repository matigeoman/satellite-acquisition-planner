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
    "schedule_history": "Historia_planow",
    "stk_access_matches": "STK_Access",
    "stk_aer_matches": "STK_AER",
}


def _write_table(workbook, worksheet, rows, header_format, percent_format) -> None:
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

    overview = workbook.add_worksheet("Podsumowanie")
    overview.hide_gridlines(2)
    overview.write("A1", snapshot.title, title)
    overview.write("A2", snapshot.project_name, subtitle)
    overview.write("A4", "ID projektu", metric_label)
    overview.write("B4", snapshot.project_id, metric_value)
    overview.write("A5", "Autor", metric_label)
    overview.write("B5", snapshot.author or "nie podano", metric_value)
    overview.write("A6", "Instytucja", metric_label)
    overview.write("B6", snapshot.institution or "nie podano", metric_value)
    overview.write("A7", "Wygenerowano UTC", metric_label)
    overview.write("B7", snapshot.generated_at_utc.isoformat(), metric_value)
    overview.write("A9", "Metryka", header)
    overview.write("B9", "Wartość", header)
    overview.write("C9", "Jednostka", header)
    for index, item in enumerate(snapshot.overview_metrics, start=10):
        overview.write(index - 1, 0, item["metric"], metric_label)
        overview.write(index - 1, 1, item["value"], metric_value)
        overview.write(index - 1, 2, item.get("unit", ""), metric_value)
    overview.set_column("A:A", 34)
    overview.set_column("B:B", 24)
    overview.set_column("C:C", 12)

    for key, rows in snapshot.table_map().items():
        worksheet = workbook.add_worksheet(_SHEET_NAMES[key])
        _write_table(workbook, worksheet, rows, header, percent)

    if snapshot.benchmark_summary_rows:
        sheet = workbook.get_worksheet_by_name("Benchmark_summary")
        columns = list(snapshot.benchmark_summary_rows[0])
        if "request_count" in columns and "objective_mean" in columns:
            request_col = columns.index("request_count")
            objective_col = columns.index("objective_mean")
            chart = workbook.add_chart({"type": "line"})
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
            sheet.insert_chart("Q2", chart, {"x_scale": 1.25, "y_scale": 1.1})

    workbook.close()
    return buffer.getvalue()
