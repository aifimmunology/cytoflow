"""Stats1D view — go.Scatter with error bars, one statistic vs variable."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from .base import (register, HUE_COLORS, BASE_LAYOUT, placeholder_figure)


@register("cytoflow.view.stats1d")
def render(experiment, params: dict) -> dict:
    statistic = params.get("statistic")
    if not statistic or statistic not in experiment.statistics:
        avail = list(experiment.statistics.keys())
        return placeholder_figure(
            f"Statistic '{statistic}' not found." if not avail
            else f"Available statistics: {avail}"
        )

    stat = experiment.statistics[statistic]
    feature = params.get("feature") or (stat.columns[0] if hasattr(stat, "columns") and len(stat.columns) else None)
    error_low = params.get("error_low")
    error_high = params.get("error_high")
    orientation = params.get("orientation", "vertical")

    if hasattr(stat.index, "levels"):
        var_labels = [" | ".join(str(v) for v in idx) for idx in stat.index]
    else:
        var_labels = [str(v) for v in stat.index]

    y_vals = stat[feature].values if feature else stat.iloc[:, 0].values
    y_err_minus = y_err_plus = None
    if error_low and error_low in stat.columns:
        y_err_minus = (y_vals - stat[error_low].values).tolist()
    if error_high and error_high in stat.columns:
        y_err_plus = (stat[error_high].values - y_vals).tolist()

    error_bar = {}
    if y_err_minus or y_err_plus:
        error_bar = dict(
            type="data",
            array=y_err_plus or y_err_minus,
            arrayminus=y_err_minus,
            visible=True,
        )

    if orientation == "horizontal":
        trace = go.Scatter(
            x=y_vals.tolist(), y=var_labels,
            mode="markers", marker=dict(color=HUE_COLORS[0], size=8),
            error_x=error_bar or None,
            name=feature or statistic,
        )
        xaxis_title = feature or statistic
        yaxis_title = ""
    else:
        trace = go.Scatter(
            x=var_labels, y=y_vals.tolist(),
            mode="markers+lines", marker=dict(color=HUE_COLORS[0], size=8),
            error_y=error_bar or None,
            name=feature or statistic,
        )
        xaxis_title = ""
        yaxis_title = feature or statistic

    fig = go.Figure(data=[trace])
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": f"{statistic} — {feature or ''}", "font": {"size": 14}},
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
    )
    return fig.to_dict()
