"""Scatterplot view — go.Scattergl (WebGL), 500k event cap."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .base import (register, HUE_COLORS, BASE_LAYOUT, sample_for_plot,
                   scale_transform, apply_scale_axes, get_facet_groups,
                   subset_df, placeholder_figure)


@register("cytoflow.view.scatterplot")
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
    huefacet = params.get("huefacet") or None
    alpha = float(params.get("alpha", 0.3))
    marker_size = int(params.get("marker_size", 3))

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

    fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=subplot_titles or None)

    x_tick_info = y_tick_info = None
    show_legend_set = set()

    for ri, rv in enumerate(row_vals):
        for ci, cv in enumerate(col_vals):
            cell = subset_df(df, rv, cv, yfacet, xfacet)
            if cell.empty:
                continue

            for hi, hv in enumerate(hue_vals):
                if hv is not None and huefacet in cell.columns:
                    hcell = cell[cell[huefacet] == hv]
                else:
                    hcell = cell
                if hcell.empty:
                    continue

                # Apply 500k cap to raw events
                hcell = sample_for_plot(hcell)

                xvals, xt = scale_transform(hcell[xchannel], xscale_name, experiment, xchannel)
                yvals, yt = scale_transform(hcell[ychannel], yscale_name, experiment, ychannel)
                if x_tick_info is None: x_tick_info = xt
                if y_tick_info is None: y_tick_info = yt

                color = HUE_COLORS[hi % len(HUE_COLORS)]
                name = str(hv) if hv is not None else f"{xchannel} vs {ychannel}"
                show_leg = name not in show_legend_set
                if show_leg:
                    show_legend_set.add(name)

                fig.add_trace(
                    go.Scattergl(
                        x=xvals.tolist(),
                        y=yvals.tolist(),
                        mode="markers",
                        marker=dict(color=color, size=marker_size, opacity=alpha),
                        name=name,
                        showlegend=show_leg,
                        legendgroup=name,
                    ),
                    row=ri + 1, col=ci + 1,
                )

    layout = dict(
        **BASE_LAYOUT,
        title={"text": f"{xchannel} vs {ychannel}", "font": {"size": 14}},
        xaxis_title=xchannel,
        yaxis_title=ychannel,
    )
    fig.update_layout(**layout)

    fig_dict = fig.to_dict()
    apply_scale_axes(fig_dict, x_tick_info, y_tick_info)
    return fig_dict
