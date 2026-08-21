"""KDE 1D view — scipy KDE on full dataset, rendered as filled go.Scatter."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import gaussian_kde
from .base import (register, HUE_COLORS, BASE_LAYOUT, scale_transform,
                   apply_scale_axes, get_facet_groups, subset_df,
                   placeholder_figure, sample_for_plot)


@register("cytoflow.view.kde1d")
def render(experiment, params: dict) -> dict:
    channel = params.get("channel") or (experiment.channels[0] if experiment.channels else None)
    if not channel or channel not in experiment.channels:
        return placeholder_figure(f"Channel '{channel}' not found")

    scale_name = params.get("scale", "linear")
    xfacet = params.get("xfacet") or None
    yfacet = params.get("yfacet") or None
    huefacet = params.get("huefacet") or None
    shade = bool(params.get("shade", True))
    num_points = int(params.get("num_points", 200))
    events_per_sample = int(params.get("events_per_sample", 500000))
    sampling_method = params.get("sampling_method", "random")

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
    x_tick_info = None
    show_legend_set = set()

    for ri, rv in enumerate(row_vals):
        for ci, cv in enumerate(col_vals):
            cell = subset_df(df, rv, cv, yfacet, xfacet)
            if cell.empty:
                continue
            cell = sample_for_plot(cell, events_per_sample=events_per_sample, method=sampling_method)

            # Global x range from the full facet cell
            x_all, tick_info = scale_transform(cell[channel], scale_name, experiment, channel)
            if x_tick_info is None:
                x_tick_info = tick_info
            x_finite = x_all[np.isfinite(x_all)]
            if len(x_finite) < 2:
                continue
            x_grid = np.linspace(x_finite.min(), x_finite.max(), num_points)

            for hi, hv in enumerate(hue_vals):
                if hv is not None and huefacet in cell.columns:
                    hcell = cell[cell[huefacet] == hv]
                else:
                    hcell = cell
                if len(hcell) < 2:
                    continue

                hx, _ = scale_transform(hcell[channel], scale_name, experiment, channel)
                hx = hx[np.isfinite(hx)]
                if len(hx) < 2:
                    continue

                try:
                    kde = gaussian_kde(hx)
                    density = kde(x_grid)
                except Exception:
                    continue

                color = HUE_COLORS[hi % len(HUE_COLORS)]
                name = str(hv) if hv is not None else channel
                show_leg = name not in show_legend_set
                if show_leg:
                    show_legend_set.add(name)

                fill = "tozeroy" if shade else None
                fig.add_trace(
                    go.Scatter(
                        x=x_grid.tolist(),
                        y=density.tolist(),
                        mode="lines",
                        fill=fill,
                        line=dict(color=color, width=2),
                        fillcolor=color.replace(")", ",0.3)").replace("rgb", "rgba") if "rgb" in color else color,
                        name=name,
                        showlegend=show_leg,
                        legendgroup=name,
                    ),
                    row=ri + 1, col=ci + 1,
                )

    layout = dict(
        **BASE_LAYOUT,
        title={"text": f"{channel} KDE ({scale_name})", "font": {"size": 14}},
        xaxis_title=channel,
        yaxis_title="Density",
    )
    fig.update_layout(**layout)

    fig_dict = fig.to_dict()
    apply_scale_axes(fig_dict, x_tick_info)
    return fig_dict
