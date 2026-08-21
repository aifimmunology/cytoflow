"""KDE 2D view — scipy 2D KDE, rendered as go.Contour."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import gaussian_kde
from .base import (register, BASE_LAYOUT, sample_for_plot, scale_transform,
                   apply_scale_axes, get_facet_groups, subset_df,
                   placeholder_figure, MAX_PLOT_EVENTS)

# KDE is O(n²) — cap at a lower limit for compute safety
_KDE_MAX = 50_000


@register("cytoflow.view.kde2d")
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
    num_points = int(params.get("num_points", 50))  # grid resolution per axis
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
            if len(xv) < 2:
                continue

            # Subsample for KDE computation
            if len(xv) > _KDE_MAX:
                idx = np.random.choice(len(xv), _KDE_MAX, replace=False)
                xv_kde, yv_kde = xv[idx], yv[idx]
            else:
                xv_kde, yv_kde = xv, yv

            try:
                kde = gaussian_kde(np.vstack([xv_kde, yv_kde]))
            except Exception:
                continue

            x_grid = np.linspace(xv.min(), xv.max(), num_points)
            y_grid = np.linspace(yv.min(), yv.max(), num_points)
            xx, yy = np.meshgrid(x_grid, y_grid)
            zz = kde(np.vstack([xx.ravel(), yy.ravel()])).reshape(num_points, num_points)

            fig.add_trace(
                go.Contour(
                    z=zz.tolist(),
                    x=x_grid.tolist(),
                    y=y_grid.tolist(),
                    colorscale="Blues",
                    showscale=(ri == 0 and ci == 0),
                    contours_coloring="heatmap",
                ),
                row=ri + 1, col=ci + 1,
            )

    layout = dict(
        **BASE_LAYOUT,
        title={"text": f"{xchannel} vs {ychannel} (KDE)", "font": {"size": 14}},
        xaxis_title=xchannel,
        yaxis_title=ychannel,
    )
    fig.update_layout(**layout)

    fig_dict = fig.to_dict()
    apply_scale_axes(fig_dict, x_tick_info, y_tick_info)
    return fig_dict
