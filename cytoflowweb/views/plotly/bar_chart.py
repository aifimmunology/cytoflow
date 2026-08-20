"""Bar chart view — go.Bar from experiment statistics."""
from __future__ import annotations
import plotly.graph_objects as go
from .base import (register, HUE_COLORS, BASE_LAYOUT, scale_transform,
                   apply_scale_axes, placeholder_figure)


@register("cytoflow.view.barchart")
def render(experiment, params: dict) -> dict:
    statistic = params.get("statistic")
    if not statistic or statistic not in experiment.statistics:
        avail = list(experiment.statistics.keys())
        return placeholder_figure(
            f"Statistic '{statistic}' not found. Available: {avail}" if avail
            else "No statistics available. Run a statistics operation first."
        )

    stat = experiment.statistics[statistic]
    feature = params.get("feature") or (stat.columns[0] if hasattr(stat, "columns") and len(stat.columns) else None)
    error_low = params.get("error_low")
    error_high = params.get("error_high")
    scale_name = params.get("scale", "linear")
    huefacet = params.get("huefacet") or None
    orientation = params.get("orientation", "vertical")  # "vertical" or "horizontal"

    if feature and feature not in stat.columns:
        return placeholder_figure(f"Feature '{feature}' not in statistic columns: {list(stat.columns)}")

    # Flatten the statistic index into x-axis labels
    if hasattr(stat.index, "levels"):
        x_labels = [" | ".join(str(v) for v in idx) for idx in stat.index]
    else:
        x_labels = [str(v) for v in stat.index]

    y_vals = stat[feature].values.tolist() if feature else stat.iloc[:, 0].values.tolist()

    err_minus = err_plus = None
    if error_low and error_low in stat.columns:
        err_minus = (stat[feature] - stat[error_low]).abs().values.tolist()
    if error_high and error_high in stat.columns:
        err_plus = (stat[error_high] - stat[feature]).abs().values.tolist()

    error_bar = {}
    if err_minus or err_plus:
        error_bar = dict(
            type="data",
            array=err_plus or err_minus,
            arrayminus=err_minus,
            visible=True,
        )

    if orientation == "horizontal":
        bar = go.Bar(x=y_vals, y=x_labels, orientation="h",
                     marker_color=HUE_COLORS[0], error_x=error_bar or None,
                     name=feature or statistic)
        xaxis_title = feature or statistic
        yaxis_title = ""
    else:
        bar = go.Bar(x=x_labels, y=y_vals, orientation="v",
                     marker_color=HUE_COLORS[0], error_y=error_bar or None,
                     name=feature or statistic)
        xaxis_title = ""
        yaxis_title = feature or statistic

    fig = go.Figure(data=[bar])
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": f"{statistic} — {feature or ''}", "font": {"size": 14}},
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
    )

    return fig.to_dict()
