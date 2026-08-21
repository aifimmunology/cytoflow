"""Violin view — go.Violin per condition group, 500k event cap."""
from __future__ import annotations
import plotly.graph_objects as go
from .base import (register, HUE_COLORS, BASE_LAYOUT, sample_for_plot,
                   scale_transform, apply_scale_axes, placeholder_figure)


@register("cytoflow.view.violin")
def render(experiment, params: dict) -> dict:
    channel = params.get("channel") or (experiment.channels[0] if experiment.channels else None)
    if not channel or channel not in experiment.channels:
        return placeholder_figure(f"Channel '{channel}' not found")

    scale_name = params.get("scale", "linear")
    groupby = params.get("groupby") or None  # condition to group violins
    points = params.get("points", "outliers")  # "all", "outliers", False
    events_per_sample = int(params.get("events_per_sample", 500000))
    sampling_method = params.get("sampling_method", "random")

    df = experiment.data
    group_vals = [None]
    if groupby and groupby in df.columns:
        from natsort import natsorted
        group_vals = natsorted(df[groupby].unique().tolist())

    traces = []
    x_tick_info = None

    for hi, gv in enumerate(group_vals):
        if gv is not None:
            cell = df[df[groupby] == gv]
        else:
            cell = df

        cell = sample_for_plot(cell, events_per_sample=events_per_sample, method=sampling_method)
        vals, tick_info = scale_transform(cell[channel], scale_name, experiment, channel)
        if x_tick_info is None:
            x_tick_info = tick_info

        color = HUE_COLORS[hi % len(HUE_COLORS)]
        name = str(gv) if gv is not None else channel

        traces.append(go.Violin(
            y=vals.tolist(),
            name=name,
            line_color=color,
            fillcolor=color,
            opacity=0.6,
            box_visible=True,
            meanline_visible=True,
            points=points,
        ))

    import plotly.graph_objects as _go
    fig = _go.Figure(data=traces)
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": f"{channel} distribution ({scale_name})", "font": {"size": 14}},
        yaxis_title=channel,
        xaxis_title=groupby or "",
        violinmode="group",
    )

    fig_dict = fig.to_dict()
    # Violin y-axis gets the scale ticks
    apply_scale_axes(fig_dict, x_tick_info=None, y_tick_info=x_tick_info)
    return fig_dict
