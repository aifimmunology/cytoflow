"""MST view — go.Scatter edges + nodes from a statistic, igraph for layout."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from .base import (register, HUE_COLORS, BASE_LAYOUT, placeholder_figure)


@register("cytoflow.view.mst")
def render(experiment, params: dict) -> dict:
    statistic = params.get("statistic")
    locations = params.get("locations")  # statistic with x,y coordinates

    if not statistic or statistic not in experiment.statistics:
        avail = list(experiment.statistics.keys())
        return placeholder_figure("No statistics available." if not avail else f"Available: {avail}")

    try:
        import igraph
        import scipy.spatial.distance as ssd
    except ImportError as exc:
        return placeholder_figure(f"MST view requires igraph and scipy: {exc}")

    stat = experiment.statistics[statistic]
    feature = params.get("feature") or (stat.columns[0] if hasattr(stat, "columns") and len(stat.columns) else None)
    metric = params.get("metric", "euclidean")

    # If a locations statistic is provided, use it for node XY positions
    locs_stat = experiment.statistics.get(locations) if locations else None

    values = stat[feature].values if feature else stat.iloc[:, 0].values

    # Build adjacency from distances between node values (or multi-feature vectors)
    if locs_stat is not None and len(locs_stat.columns) >= 2:
        locs_values = locs_stat.values
    else:
        # Fall back to 1D distances
        locs_values = values.reshape(-1, 1)

    dist_matrix = ssd.cdist(locs_values, locs_values, metric)
    full_graph = igraph.Graph.Weighted_Adjacency(
        dist_matrix.tolist(), mode="undirected", loops=False
    )
    mst = igraph.Graph.spanning_tree(full_graph, weights=full_graph.es["weight"])
    mst.es["weight"] = [w / (np.mean(mst.es["weight"]) or 1.0) for w in mst.es["weight"]]

    layout = mst.layout_kamada_kawai(
        seed=mst.layout_grid(),
        maxiter=50 * mst.vcount(),
        kkconst=max(mst.vcount(), 1),
    )
    coords = np.array(layout.coords)  # (n_nodes, 2)

    # Build edge traces
    edge_x, edge_y = [], []
    for edge in mst.get_edgelist():
        x0, y0 = coords[edge[0]]
        x1, y1 = coords[edge[1]]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(color="#aaa", width=1),
        showlegend=False, hoverinfo="skip",
    )

    # Node labels from index
    if hasattr(stat.index, "levels"):
        node_labels = [" | ".join(str(v) for v in idx) for idx in stat.index]
    else:
        node_labels = [str(v) for v in stat.index]

    # Node sizes proportional to values
    v_min, v_max = np.nanmin(values), np.nanmax(values)
    v_range = v_max - v_min if v_max != v_min else 1.0
    node_sizes = 10 + 30 * (values - v_min) / v_range

    node_trace = go.Scatter(
        x=coords[:, 0].tolist(),
        y=coords[:, 1].tolist(),
        mode="markers+text",
        text=node_labels,
        textposition="top center",
        hovertext=[f"{l}: {v:.3g}" for l, v in zip(node_labels, values)],
        hovertemplate="%{hovertext}<extra></extra>",
        marker=dict(
            size=node_sizes.tolist(),
            color=values.tolist(),
            colorscale="Viridis",
            showscale=True,
            colorbar={"title": feature or statistic},
        ),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": f"MST — {statistic}", "font": {"size": 14}},
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig.to_dict()
