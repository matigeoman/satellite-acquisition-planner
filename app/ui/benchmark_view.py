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


def _single_request_count(frame: pd.DataFrame) -> int | None:
    if frame.empty or "request_count" not in frame.columns:
        return None
    values = frame["request_count"].dropna().unique().tolist()
    if len(values) != 1:
        return None
    return int(values[0])


def _single_count_bar_figure(
    frame: pd.DataFrame,
    *,
    value_column: str,
    value_label: str,
    title: str,
    log_y: bool = False,
) -> Figure:
    request_count = _single_request_count(frame)
    figure = px.bar(
        frame,
        x="algorithm_variant",
        y=value_column,
        color="algorithm_variant",
        labels={
            "algorithm_variant": "Wariant",
            value_column: value_label,
        },
        title=(
            f"{title} — {request_count} zleceń" if request_count is not None else title
        ),
    )
    figure.update_layout(showlegend=False)
    if log_y:
        figure.update_yaxes(type="log")
    return figure


def build_benchmark_runtime_figure(
    result: AlgorithmBenchmarkResult,
) -> Figure:
    frame = build_benchmark_summary_dataframe(result)
    if _single_request_count(frame) is not None:
        figure = _single_count_bar_figure(
            frame,
            value_column="runtime_mean_s",
            value_label="Średni czas [s] — skala log",
            title="Czas obliczeń względem rozmiaru problemu",
            log_y=True,
        )
    else:
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
    if _single_request_count(frame) is not None:
        figure = _single_count_bar_figure(
            frame,
            value_column="objective_mean",
            value_label="Średnia wartość funkcji celu",
            title="Jakość harmonogramu",
        )
    else:
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
    frame = build_benchmark_summary_dataframe(result).copy()
    frame["satisfaction_percent"] = frame["satisfaction_ratio_mean"] * 100.0
    if _single_request_count(frame) is not None:
        figure = _single_count_bar_figure(
            frame,
            value_column="satisfaction_percent",
            value_label="Zrealizowane zlecenia [%]",
            title="Stopień realizacji zleceń",
        )
    else:
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
    grouped["variant"] = grouped["time_limit_s"].map(lambda value: f"CP-SAT {value:g}s")
    request_count = _single_request_count(grouped)
    if request_count is not None:
        figure = px.bar(
            grouped,
            x="variant",
            y="objective_improvement_pct",
            color="variant",
            labels={
                "variant": "Wariant",
                "objective_improvement_pct": "Przewaga nad Greedy [%]",
            },
            title=(
                f"Zmiana funkcji celu CP-SAT względem Greedy — {request_count} zleceń"
            ),
        )
        figure.update_layout(showlegend=False)
    else:
        grouped["request_count_label"] = grouped["request_count"].map(str)
        figure = px.bar(
            grouped,
            x="request_count_label",
            y="objective_improvement_pct",
            color="variant",
            barmode="group",
            labels={
                "request_count_label": "Liczba zleceń",
                "objective_improvement_pct": "Przewaga nad Greedy [%]",
                "variant": "Wariant",
            },
            title="Zmiana funkcji celu CP-SAT względem Greedy",
        )
    figure.add_hline(y=0)
    figure.update_layout(uirevision="benchmark-improvement")
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
    frame = frame[frame["count"] > 0.0]
    if frame.empty:
        return Figure().update_layout(
            title="Brak odrzuceń operacyjnych w poprawnych przebiegach"
        )
    frame["reason_label"] = frame["reason"].map(labels)
    frame["request_count_label"] = frame["request_count"].map(str)
    unique_counts = frame["request_count_label"].nunique()
    figure = px.bar(
        frame,
        x="algorithm_variant",
        y="count",
        color="reason_label",
        facet_col="request_count_label",
        facet_col_wrap=min(3, unique_counts),
        barmode="stack",
        labels={
            "algorithm_variant": "Wariant",
            "count": "Średnia liczba odrzuceń",
            "reason_label": "Przyczyna",
            "request_count_label": "Liczba zleceń",
        },
        title="Przyczyny niezrealizowania zleceń",
    )
    figure.for_each_annotation(
        lambda annotation: annotation.update(
            text=annotation.text.replace(
                "request_count_label=", "Liczba zleceń: "
            ).replace("Liczba zleceń=", "Liczba zleceń: ")
        )
    )
    figure.update_layout(uirevision="benchmark-rejections")
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
