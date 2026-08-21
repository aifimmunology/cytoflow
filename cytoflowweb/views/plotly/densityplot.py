"""Density plot — np.histogram2d server-side, go.Heatmap."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .base import (register, BASE_LAYOUT, scale_transform, apply_scale_axes,
                   get_facet_groups, subset_df, placeholder_figure, sample_for_plot)


@register("cytoflow.view.density")
def render(experiment, params: dict) -> dict:
    channels = experiment.channels
    xchannel = params.get("xchannel") or (channels[0] if len(channels) > 0 else None)
    ychannel = params.get("ychannel") or (channels[1] if len(channels) > 1 else None)
    if not xchannel or xchannel not in channels:
        return placeholder_figure(f"xchannel '{xchannel}' not found")
    if not ychannel or ychannel not in channels:
        return placeholder_figure(f"ychannel '{ychannel}' not found")

    xscale_name = params.get("xscale", "linear")
    yscale_name = params.get("yscale", "linear")
    xfacet = params.get("xfacet") or None
    yfacet = params.get("yfacet") or None
    num_bins = int(params.get("num_bins", 100))
    events_per_sample = int(params.get("events_per_sample", 500000))
    sampling_method = params.get("sampling_method", "random")

    df = experiment.data
    fg = get_facet_groups(df, xfacet, yfacet, None)
    n_rows, n_cols = fg["n_rows"], fg["n_cols"]
    row_vals, col_vals = fg["row_vals"], fg["col_vals"]

    subplot_titles = []
    for rv in row_vals:
        for cv in col_vals:
            parts = []
            if rv is not None: parts.append(f"{yfacet}={rv}")
            if cv is not None: parts.append(f"{xfacet}={cv}")
            subplot_titles.append(" | ".join(parts))

    fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=subplot_titles or None)
    x_tick_info = y_tick_info = None

    for ri, rv in enumerate(row_vals):
        for ci, cv in enumerate(col_vals):
            cell = subset_df(df, rv, cv, yfacet, xfacet)
            if cell.empty:
                continue
            cell = sample_for_plot(cell, events_per_sample=events_per_sample, method=sampling_method)

            xvals, xt = scale_transform(cell[xchannel], xscale_name, experiment, xchannel)
            yvals, yt = scale_transform(cell[ychannel], yscale_name, experiment, ychannel)
            if x_tick_info is None: x_tick_info = xt
            if y_tick_info is None: y_tick_info = yt

            mask = np.isfinite(xvals) & np.isfinite(yvals)
            xv, yv = xvals[mask], yvals[mask]
            if len(xv) == 0:
                continue

            counts, xedges, yedges = np.histogram2d(xv, yv, bins=num_bins)
            xcenters = (xedges[:-1] + xedges[1:]) / 2
            ycenters = (yedges[:-1] + yedges[1:]) / 2

            fig.add_trace(
                go.Heatmap(
                    z=counts.T.tolist(),
                    x=xcenters.tolist(),
                    y=ycenters.tolist(),
                    colorscale="Hot",
                    reversescale=True,
                    showscale=(ri == 0 and ci == 0),
                    colorbar={"title": "Count"},
                ),
                row=ri + 1, col=ci + 1,
            )

    layout = dict(
        **BASE_LAYOUT,
        title={"text": f"{xchannel} vs {ychannel} (density)", "font": {"size": 14}},
        xaxis_title=xchannel,
        yaxis_title=ychannel,
    )
    fig.update_layout(**layout)

    fig_dict = fig.to_dict()
    apply_scale_axes(fig_dict, x_tick_info, y_tick_info)
    return fig_dict
