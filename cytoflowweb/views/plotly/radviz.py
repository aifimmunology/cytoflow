"""Radviz view — unit circle anchors + event projections via go.Scatter."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from .base import (register, HUE_COLORS, BASE_LAYOUT, sample_for_plot,
                   scale_transform, placeholder_figure)


@register("cytoflow.view.radviz")
def render(experiment, params: dict) -> dict:
    channels = params.get("channels") or experiment.channels
    if not channels:
        return placeholder_figure("No channels selected")
    channels = [c for c in channels if c in experiment.channels]
    if len(channels) < 3:
        return placeholder_figure("Radviz requires at least 3 channels")

    scale_map = params.get("scale", {})
    huefacet = params.get("huefacet") or None
    events_per_sample = int(params.get("events_per_sample", 500000))
    sampling_method = params.get("sampling_method", "random")

    df = sample_for_plot(experiment.data, events_per_sample=events_per_sample, method=sampling_method)

    # Build the normalised data matrix (channels x events) in scale space
    arrays = []
    for ch in channels:
        scale_name = scale_map.get(ch, "linear") if isinstance(scale_map, dict) else "linear"
        vals, _ = scale_transform(df[ch], scale_name, experiment, ch)
        arrays.append(vals)
    data_matrix = np.column_stack(arrays)  # (n_events, n_channels)

    # Clip non-finite
    data_matrix = np.where(np.isfinite(data_matrix), data_matrix, 0.0)

    # Normalise each event to [0,1] per channel (min-max across all events)
    col_min = np.nanmin(data_matrix, axis=0)
    col_max = np.nanmax(data_matrix, axis=0)
    col_range = np.where(col_max - col_min > 0, col_max - col_min, 1.0)
    norm = (data_matrix - col_min) / col_range  # (n_events, n_channels)

    # Anchor positions evenly on unit circle
    n_ch = len(channels)
    angles = np.linspace(0, 2 * np.pi, n_ch, endpoint=False)
    anchors = np.column_stack([np.cos(angles), np.sin(angles)])  # (n_channels, 2)

    # Radviz projection: weighted sum of anchor vectors
    weights = norm  # (n_events, n_channels)
    weight_sum = weights.sum(axis=1, keepdims=True)
    weight_sum = np.where(weight_sum == 0, 1.0, weight_sum)
    proj = (weights / weight_sum) @ anchors  # (n_events, 2)

    traces = []

    # Event points, coloured by hue
    if huefacet and huefacet in df.columns:
        from natsort import natsorted
        hue_vals = natsorted(df[huefacet].unique().tolist())
        hue_series = df[huefacet].values
        for hi, hv in enumerate(hue_vals):
            mask = hue_series == hv
            color = HUE_COLORS[hi % len(HUE_COLORS)]
            traces.append(go.Scattergl(
                x=proj[mask, 0].tolist(), y=proj[mask, 1].tolist(),
                mode="markers",
                marker=dict(color=color, size=2, opacity=0.4),
                name=str(hv),
            ))
    else:
        traces.append(go.Scattergl(
            x=proj[:, 0].tolist(), y=proj[:, 1].tolist(),
            mode="markers",
            marker=dict(color=HUE_COLORS[0], size=2, opacity=0.3),
            name="events",
            showlegend=False,
        ))

    # Unit circle
    theta = np.linspace(0, 2 * np.pi, 200)
    traces.append(go.Scatter(
        x=np.cos(theta).tolist(), y=np.sin(theta).tolist(),
        mode="lines", line=dict(color="#aaa", width=1),
        showlegend=False, hoverinfo="skip",
    ))

    # Anchor spokes and labels
    for i, ch in enumerate(channels):
        ax, ay = float(anchors[i, 0]), float(anchors[i, 1])
        traces.append(go.Scatter(
            x=[0, ax], y=[0, ay],
            mode="lines+text",
            line=dict(color="#555", width=1),
            text=["", ch],
            textposition="top center",
            showlegend=False, hoverinfo="skip",
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": f"Radviz ({len(channels)} channels)", "font": {"size": 14}},
        xaxis=dict(visible=False, range=[-1.3, 1.3]),
        yaxis=dict(visible=False, range=[-1.3, 1.3], scaleanchor="x"),
        hovermode="closest",
    )
    return fig.to_dict()
