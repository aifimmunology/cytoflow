"""Matrix view — go.Heatmap from a statistic with a 2-level MultiIndex."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from .base import (register, BASE_LAYOUT, placeholder_figure)


@register("cytoflow.view.matrix")
def render(experiment, params: dict) -> dict:
    statistic = params.get("statistic")
    if not statistic or statistic not in experiment.statistics:
        avail = list(experiment.statistics.keys())
        return placeholder_figure("No statistics available." if not avail else f"Available: {avail}")

    stat = experiment.statistics[statistic]
    feature = params.get("feature") or (stat.columns[0] if hasattr(stat, "columns") and len(stat.columns) else None)

    if feature and feature not in stat.columns:
        return placeholder_figure(f"Feature '{feature}' not in statistic: {list(stat.columns)}")

    values = stat[feature] if feature else stat.iloc[:, 0]

    if not hasattr(values.index, "levels") or len(values.index.levels) < 2:
        return placeholder_figure(
            "MatrixView requires a statistic with a 2-level MultiIndex. "
            "Use a groupby operation that produces two condition levels."
        )

    from natsort import natsorted
    row_labels = natsorted([str(v) for v in values.index.get_level_values(0).unique()])
    col_labels = natsorted([str(v) for v in values.index.get_level_values(1).unique()])

    z = []
    for rl in row_labels:
        row = []
        for cl in col_labels:
            try:
                row.append(float(values.loc[(rl, cl)]))
            except (KeyError, TypeError):
                row.append(float("nan"))
        z.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=col_labels,
        y=row_labels,
        colorscale="RdBu",
        zmid=0,
        colorbar={"title": feature or statistic},
    ))
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": f"{statistic} — {feature or ''}", "font": {"size": 14}},
    )
    return fig.to_dict()
