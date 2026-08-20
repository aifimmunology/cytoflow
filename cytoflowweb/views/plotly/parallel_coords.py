"""Parallel coordinates view — go.Parcoords with per-channel scale transform."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from .base import (register, BASE_LAYOUT, sample_for_plot, scale_transform,
                   placeholder_figure)


@register("cytoflow.view.parallel_coords")
def render(experiment, params: dict) -> dict:
    channels = params.get("channels") or experiment.channels
    if not channels:
        return placeholder_figure("No channels selected")

    # Filter to channels that exist
    channels = [c for c in channels if c in experiment.channels]
    if not channels:
        return placeholder_figure("None of the requested channels exist in the experiment")

    scale_map = params.get("scale", {})  # dict channel->scale_name
    huefacet = params.get("huefacet") or None

    df = sample_for_plot(experiment.data)

    dimensions = []
    for ch in channels:
        scale_name = scale_map.get(ch, "linear") if isinstance(scale_map, dict) else "linear"
        vals, tick_info = scale_transform(df[ch], scale_name, experiment, ch)
        dim = dict(
            label=ch,
            values=vals.tolist(),
        )
        if tick_info:
            tickvals, ticktext = tick_info
            dim["tickvals"] = tickvals
            dim["ticktext"] = ticktext
        dimensions.append(dim)

    # Optional color by hue condition
    line_opts = dict(color=HUE_COLORS[0] if not huefacet else None)
    if huefacet and huefacet in df.columns:
        from natsort import natsorted
        hue_vals = natsorted(df[huefacet].unique().tolist())
        color_map = {v: i for i, v in enumerate(hue_vals)}
        color_nums = df[huefacet].map(color_map).values.tolist()
        line_opts = dict(
            color=color_nums,
            colorscale="Turbo",
            showscale=True,
            colorbar=dict(
                title=huefacet,
                tickvals=list(color_map.values()),
                ticktext=list(color_map.keys()),
            ),
        )

    trace = go.Parcoords(
        line=line_opts,
        dimensions=dimensions,
    )

    fig = go.Figure(data=[trace])
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": f"Parallel Coordinates ({len(channels)} channels)", "font": {"size": 14}},
    )
    return fig.to_dict()


# Need HUE_COLORS for the non-hue path
from .base import HUE_COLORS
