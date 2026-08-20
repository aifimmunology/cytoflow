"""Stats2D view — go.Scatter with x+y error bars from two statistic features."""
from __future__ import annotations
import plotly.graph_objects as go
from .base import (register, HUE_COLORS, BASE_LAYOUT, placeholder_figure)


@register("cytoflow.view.stats2d")
def render(experiment, params: dict) -> dict:
    statistic = params.get("statistic")
    if not statistic or statistic not in experiment.statistics:
        avail = list(experiment.statistics.keys())
        return placeholder_figure(
            "No statistics available." if not avail else f"Available: {avail}"
        )

    stat = experiment.statistics[statistic]
    xfeature = params.get("xfeature") or (stat.columns[0] if len(stat.columns) > 0 else None)
    yfeature = params.get("yfeature") or (stat.columns[1] if len(stat.columns) > 1 else None)

    for f in [xfeature, yfeature]:
        if f and f not in stat.columns:
            return placeholder_figure(f"Feature '{f}' not in statistic columns: {list(stat.columns)}")

    xvals = stat[xfeature].values.tolist() if xfeature else []
    yvals = stat[yfeature].values.tolist() if yfeature else []

    def _error_bar(lo_key, hi_key, center):
        lo = stat[lo_key].values if lo_key and lo_key in stat.columns else None
        hi = stat[hi_key].values if hi_key and hi_key in stat.columns else None
        if lo is None and hi is None:
            return None
        return dict(
            type="data",
            array=(hi - center).tolist() if hi is not None else None,
            arrayminus=(center - lo).tolist() if lo is not None else None,
            visible=True,
        )

    xerr = _error_bar(params.get("xerror_low"), params.get("xerror_high"),
                      stat[xfeature].values if xfeature else None)
    yerr = _error_bar(params.get("yerror_low"), params.get("yerror_high"),
                      stat[yfeature].values if yfeature else None)

    # Use multi-index as hover text
    if hasattr(stat.index, "levels"):
        labels = [" | ".join(str(v) for v in idx) for idx in stat.index]
    else:
        labels = [str(v) for v in stat.index]

    trace = go.Scatter(
        x=xvals, y=yvals,
        mode="markers",
        marker=dict(color=HUE_COLORS[0], size=8),
        text=labels,
        hovertemplate="%{text}<extra></extra>",
        error_x=xerr,
        error_y=yerr,
        name=f"{xfeature} vs {yfeature}",
    )

    fig = go.Figure(data=[trace])
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": f"{statistic}: {xfeature} vs {yfeature}", "font": {"size": 14}},
        xaxis_title=xfeature or "",
        yaxis_title=yfeature or "",
    )
    return fig.to_dict()
