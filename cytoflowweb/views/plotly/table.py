"""Table views — return DataTable-compatible dicts instead of Plotly figures."""
from __future__ import annotations
from .base import register, placeholder_figure


def _stat_to_table(experiment, statistic: str) -> dict:
    """Convert a statistic DataFrame to a {type, columns, data} dict."""
    if not statistic or statistic not in experiment.statistics:
        avail = list(experiment.statistics.keys())
        return {
            "type": "error",
            "message": f"Statistic '{statistic}' not found. Available: {avail}",
        }

    stat = experiment.statistics[statistic]

    # Reset multi-index to columns for display
    df = stat.reset_index()

    columns = [{"name": str(c), "id": str(c)} for c in df.columns]
    data = []
    for _, row in df.iterrows():
        data.append({str(c): _fmt_cell(row[c]) for c in df.columns})

    return {
        "type": "table",
        "columns": columns,
        "data": data,
        "title": statistic,
    }


def _fmt_cell(val) -> str:
    if hasattr(val, "item"):
        val = val.item()
    if isinstance(val, float):
        return f"{val:.4g}"
    return str(val)


@register("cytoflow.view.table")
def render_table(experiment, params: dict) -> dict:
    statistic = params.get("statistic")
    return _stat_to_table(experiment, statistic)


@register("cytoflow.view.long_table")
def render_long_table(experiment, params: dict) -> dict:
    statistic = params.get("statistic")
    return _stat_to_table(experiment, statistic)
