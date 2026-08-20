"""Histogram view — pre-binned go.Bar, per-hue overlay, faceting."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .base import (register, HUE_COLORS, BASE_LAYOUT, MAX_PLOT_EVENTS,
                   scale_transform, apply_scale_axes, get_facet_groups,
                   subset_df, placeholder_figure)


@register("cytoflow.view.histogram")
def render(experiment, params: dict) -> dict:
    channel = params.get("channel") or (experiment.channels[0] if experiment.channels else None)
    if not channel or channel not in experiment.channels:
        return placeholder_figure(f"Channel '{channel}' not found")

    scale_name = params.get("scale", "linear")
    xfacet = params.get("xfacet") or None
    yfacet = params.get("yfacet") or None
    huefacet = params.get("huefacet") or None
    num_bins = int(params.get("num_bins", 256))

    df = experiment.data
    fg = get_facet_groups(df, xfacet, yfacet, huefacet)
    n_rows, n_cols = fg["n_rows"], fg["n_cols"]
    row_vals, col_vals, hue_vals = fg["row_vals"], fg["col_vals"], fg["hue_vals"]

    subplot_titles = []
    for rv in row_vals:
        for cv in col_vals:
            parts = []
            if rv is not None: parts.append(f"{yfacet}={rv}")
            if cv is not None: parts.append(f"{xfacet}={cv}")
            subplot_titles.append(" | ".join(parts))

    fig = make_subplots(rows=n_rows, cols=n_cols,
                        subplot_titles=subplot_titles or None,
                        shared_xaxes=True, shared_yaxes=False)

    x_tick_info = None
    show_legend_set = set()

    for ri, rv in enumerate(row_vals):
        for ci, cv in enumerate(col_vals):
            cell = subset_df(df, rv, cv, yfacet, xfacet)
            if cell.empty:
                continue

            # Compute global bin edges from the full cell data (not sampled)
            x_all, tick_info = scale_transform(cell[channel], scale_name, experiment, channel)
            if x_tick_info is None:
                x_tick_info = tick_info

            x_finite = x_all[np.isfinite(x_all)]
            if len(x_finite) == 0:
                continue
            bin_edges = np.linspace(x_finite.min(), x_finite.max(), num_bins + 1)
            bin_width = bin_edges[1] - bin_edges[0]
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

            for hi, hv in enumerate(hue_vals):
                if hv is not None and huefacet in cell.columns:
                    hcell = cell[cell[huefacet] == hv]
                else:
                    hcell = cell
                if hcell.empty:
                    continue

                hx, _ = scale_transform(hcell[channel], scale_name, experiment, channel)
                counts, _ = np.histogram(hx[np.isfinite(hx)], bins=bin_edges)
                color = HUE_COLORS[hi % len(HUE_COLORS)]
                name = str(hv) if hv is not None else channel
                show_leg = name not in show_legend_set
                if show_leg:
                    show_legend_set.add(name)

                fig.add_trace(
                    go.Bar(
                        x=bin_centers.tolist(),
                        y=counts.tolist(),
                        width=float(bin_width),
                        marker_color=color,
                        name=name,
                        showlegend=show_leg,
                        legendgroup=name,
                    ),
                    row=ri + 1, col=ci + 1,
                )

    layout = dict(
        **BASE_LAYOUT,
        title={"text": f"{channel} ({scale_name})", "font": {"size": 14}},
        xaxis_title=channel,
        yaxis_title="Count",
        bargap=0,
        barmode="overlay",
        hovermode="x unified",
    )
    fig.update_layout(**layout)

    fig_dict = fig.to_dict()
    apply_scale_axes(fig_dict, x_tick_info)
    return fig_dict
