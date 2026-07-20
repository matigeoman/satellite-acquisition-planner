from __future__ import annotations

import json
from dataclasses import asdict
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import plotly.express as px
import plotly.io as pio
from plotly.graph_objects import Figure

from app.analysis.algorithm_benchmark import AlgorithmBenchmarkResult


REJECTION_COLUMNS = [
    "transition_rejections",
    "memory_rejections",
    "acquisition_limit_rejections",
    "imaging_time_rejections",
    "dual_separation_rejections",
]


def build_benchmark_runs_dataframe(
    result: AlgorithmBenchmarkResult,
) -> pd.DataFrame:
    rows = []
    for record in result.run_records:
        row = asdict(record)
        row["algorithm_variant"] = record.algorithm_variant
        row["successful"] = record.successful
        rows.append(row)
    return pd.DataFrame(rows)


def build_benchmark_pairs_dataframe(
    result: AlgorithmBenchmarkResult,
) -> pd.DataFrame:
    return pd.DataFrame([asdict(record) for record in result.pair_records])


def build_benchmark_summary_dataframe(
    result: AlgorithmBenchmarkResult,
) -> pd.DataFrame:
    rows = []
    for record in result.summary_records:
        row = asdict(record)
        row["algorithm_variant"] = record.algorithm_variant
        rows.append(row)
    return pd.DataFrame(rows)


def build_benchmark_rejections_dataframe(
    result: AlgorithmBenchmarkResult,
) -> pd.DataFrame:
    runs = build_benchmark_runs_dataframe(result)
    successful = runs[runs["successful"]]
    if successful.empty:
        return pd.DataFrame(
            columns=["request_count", "algorithm_variant", "reason", "count"]
        )
    grouped = (
        successful.groupby(
            ["request_count", "algorithm_variant"],
            as_index=False,
        )[REJECTION_COLUMNS]
        .mean()
        .melt(
            id_vars=["request_count", "algorithm_variant"],
            var_name="reason",
            value_name="count",
        )
    )
    return grouped


def build_benchmark_runtime_figure(
    result: AlgorithmBenchmarkResult,
) -> Figure:
    frame = build_benchmark_summary_dataframe(result)
    figure = px.line(
        frame,
        x="request_count",
        y="runtime_mean_s",
        color="algorithm_variant",
        markers=True,
        log_y=True,
        labels={
            "request_count": "Liczba zleceń",
            "runtime_mean_s": "Średni czas [s] — skala log",
            "algorithm_variant": "Wariant",
        },
        title="Czas obliczeń względem rozmiaru problemu",
    )
    figure.update_layout(uirevision="benchmark-runtime")
    return figure


def build_benchmark_objective_figure(
    result: AlgorithmBenchmarkResult,
) -> Figure:
    frame = build_benchmark_summary_dataframe(result)
    figure = px.line(
        frame,
        x="request_count",
        y="objective_mean",
        color="algorithm_variant",
        markers=True,
        labels={
            "request_count": "Liczba zleceń",
            "objective_mean": "Średnia wartość funkcji celu",
            "algorithm_variant": "Wariant",
        },
        title="Jakość harmonogramu",
    )
    figure.update_layout(uirevision="benchmark-objective")
    return figure


def build_benchmark_satisfaction_figure(
    result: AlgorithmBenchmarkResult,
) -> Figure:
    frame = build_benchmark_summary_dataframe(result)
    frame = frame.copy()
    frame["satisfaction_percent"] = frame["satisfaction_ratio_mean"] * 100.0
    figure = px.line(
        frame,
        x="request_count",
        y="satisfaction_percent",
        color="algorithm_variant",
        markers=True,
        labels={
            "request_count": "Liczba zleceń",
            "satisfaction_percent": "Zrealizowane zlecenia [%]",
            "algorithm_variant": "Wariant",
        },
        title="Stopień realizacji zleceń",
    )
    figure.update_yaxes(range=[0, 100])
    figure.update_layout(uirevision="benchmark-satisfaction")
    return figure


def build_benchmark_improvement_figure(
    result: AlgorithmBenchmarkResult,
) -> Figure:
    frame = build_benchmark_pairs_dataframe(result)
    frame = frame[frame["cp_sat_successful"]].copy()
    if frame.empty:
        return Figure().update_layout(
            title="Brak poprawnych wyników CP-SAT do porównania"
        )
    grouped = (
        frame.groupby(["request_count", "time_limit_s"], as_index=False)[
            "objective_improvement_pct"
        ]
        .mean()
        .sort_values(["request_count", "time_limit_s"])
    )
    grouped["variant"] = grouped["time_limit_s"].map(
        lambda value: f"CP-SAT {value:g}s"
    )
    figure = px.bar(
        grouped,
        x="request_count",
        y="objective_improvement_pct",
        color="variant",
        barmode="group",
        labels={
            "request_count": "Liczba zleceń",
            "objective_improvement_pct": "Przewaga nad Greedy [%]",
            "variant": "Wariant",
        },
        title="Zmiana funkcji celu CP-SAT względem Greedy",
    )
    return figure


def build_benchmark_rejections_figure(
    result: AlgorithmBenchmarkResult,
) -> Figure:
    frame = build_benchmark_rejections_dataframe(result)
    if frame.empty:
        return Figure().update_layout(title="Brak danych diagnostycznych")
    labels = {
        "transition_rejections": "Przeorientowanie",
        "memory_rejections": "Pamięć",
        "acquisition_limit_rejections": "Limit akwizycji",
        "imaging_time_rejections": "Czas pracy sensora",
        "dual_separation_rejections": "Odstęp SAR–EO",
    }
    frame = frame.copy()
    frame["reason_label"] = frame["reason"].map(labels)
    figure = px.bar(
        frame,
        x="request_count",
        y="count",
        color="reason_label",
        facet_row="algorithm_variant",
        labels={
            "request_count": "Liczba zleceń",
            "count": "Średnia liczba odrzuceń",
            "reason_label": "Przyczyna",
        },
        title="Przyczyny niezrealizowania zleceń",
    )
    figure.for_each_annotation(
        lambda annotation: annotation.update(
            text=annotation.text.replace("algorithm_variant=", "")
        )
    )
    return figure


def build_benchmark_results_json(
    result: AlgorithmBenchmarkResult,
) -> str:
    payload = {
        "metadata": result.metadata_dict(),
        "runs": [asdict(record) for record in result.run_records],
        "pairs": [asdict(record) for record in result.pair_records],
        "summary": [asdict(record) for record in result.summary_records],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def build_benchmark_charts_html(
    result: AlgorithmBenchmarkResult,
) -> str:
    figures = [
        build_benchmark_runtime_figure(result),
        build_benchmark_objective_figure(result),
        build_benchmark_satisfaction_figure(result),
        build_benchmark_improvement_figure(result),
        build_benchmark_rejections_figure(result),
    ]
    fragments = []
    for index, figure in enumerate(figures):
        fragments.append(
            pio.to_html(
                figure,
                full_html=False,
                include_plotlyjs=True if index == 0 else False,
                config={"displaylogo": False},
            )
        )
    return (
        "<!doctype html><html lang='pl'><head><meta charset='utf-8'>"
        "<title>Benchmark Greedy vs CP-SAT</title></head><body>"
        "<h1>Benchmark Greedy vs CP-SAT</h1>"
        + "\n".join(fragments)
        + "</body></html>"
    )


def build_benchmark_export_zip(
    result: AlgorithmBenchmarkResult,
) -> bytes:
    runs = build_benchmark_runs_dataframe(result)
    pairs = build_benchmark_pairs_dataframe(result)
    summary = build_benchmark_summary_dataframe(result)
    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "benchmark_runs.csv",
            runs.to_csv(index=False).encode("utf-8-sig"),
        )
        archive.writestr(
            "benchmark_pairs.csv",
            pairs.to_csv(index=False).encode("utf-8-sig"),
        )
        archive.writestr(
            "benchmark_summary.csv",
            summary.to_csv(index=False).encode("utf-8-sig"),
        )
        archive.writestr(
            "benchmark_results.json",
            build_benchmark_results_json(result).encode("utf-8"),
        )
        archive.writestr(
            "benchmark_charts.html",
            build_benchmark_charts_html(result).encode("utf-8"),
        )
    return archive_buffer.getvalue()


__all__ = [
    "build_benchmark_charts_html",
    "build_benchmark_export_zip",
    "build_benchmark_improvement_figure",
    "build_benchmark_objective_figure",
    "build_benchmark_pairs_dataframe",
    "build_benchmark_rejections_dataframe",
    "build_benchmark_rejections_figure",
    "build_benchmark_results_json",
    "build_benchmark_runtime_figure",
    "build_benchmark_runs_dataframe",
    "build_benchmark_satisfaction_figure",
    "build_benchmark_summary_dataframe",
]
