"""
cytoflowweb.views.plotly.base
------------------------------

Shared helpers used by every Plotly view renderer.

Key utilities
-------------
sample_for_plot(df, events_per_sample, method)
    Downsample events for plotting.  If a ``Tube`` condition is present,
    applies the limit per tube (per uploaded FCS file); otherwise applies a
    global limit.

scale_transform(series, scale_name, experiment, channel)
    Apply a cytoflow scale (linear / log / logicle / hyperlog) to a
    pandas Series.  Returns the transformed array and a (tickvals, ticktext)
    tuple for fake-label axes.

make_scale(scale_name, experiment, channel)
    Return the cytoflow scale object for a channel.

apply_scale_axes(fig, xscale_info, yscale_info)
    Apply tickvals/ticktext to figure axes after building traces.

placeholder_figure(message)
    Return a minimal Plotly figure dict with a centred text annotation.

SCALE_COLORS / HUE_COLORS
    Default color palettes.

VIEW_REGISTRY
    Dict mapping view_id strings to renderer callables.
    Each renderer has signature:  render(experiment, params) -> dict
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

import cytoflow.utility as util

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_PLOT_EVENTS = 20_000

# Qualitative palette (Plotly's "Alphabet" subset, 10 colours)
HUE_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]

# Registry populated by each view module via register()
VIEW_REGISTRY: dict[str, Any] = {}


def register(view_id: str):
    """Decorator: register a render function under a view_id string."""
    def decorator(fn):
        VIEW_REGISTRY[view_id] = fn
        return fn
    return decorator


# ── Sampling ─────────────────────────────────────────────────────────────────

def sample_for_plot(
    df: pd.DataFrame,
    events_per_sample: int | None = None,
    method: str = "random",
) -> pd.DataFrame:
    """Downsample events for plotting.

    Parameters
    ----------
    df:
        Input event dataframe.
    events_per_sample:
        Number of events to keep from each sample (each distinct ``Tube`` value
        if present), or global cap when ``Tube`` is absent.
    method:
        ``"first_n"`` or ``"random"``.
    """
    if df.empty:
        return df

    n = int(events_per_sample or MAX_PLOT_EVENTS)
    if n <= 0:
        n = MAX_PLOT_EVENTS

    def _take(group: pd.DataFrame) -> pd.DataFrame:
        if len(group) <= n:
            return group
        if method == "first_n":
            return group.iloc[:n]
        return group.sample(n=n, random_state=0)

    if "Tube" in df.columns:
        return (
            df.groupby("Tube", sort=False, group_keys=False)
            .apply(_take)
            .reset_index(drop=True)
        )
    return _take(df)


# ── Scale helpers ─────────────────────────────────────────────────────────────

def make_scale(scale_name: str, experiment, channel: str):
    """Return a cytoflow scale object (callable, has .inverse())."""
    try:
        return util.scale_factory(scale_name, experiment, channel=channel)
    except Exception:
        return util.scale_factory("linear", experiment, channel=channel)


def scale_transform(
    series: pd.Series,
    scale_name: str,
    experiment,
    channel: str,
) -> tuple[np.ndarray, tuple[list, list] | None]:
    """Transform ``series`` by ``scale_name`` and return (transformed, tick_info).

    tick_info is (tickvals_in_transformed_space, ticktext_labels) or None for
    linear scale (Plotly handles linear natively).
    """
    scale = make_scale(scale_name, experiment, channel)
    transformed = np.asarray(scale(series.values), dtype=float)

    if scale_name == "linear":
        return transformed, None

    tick_info = _build_tick_info(scale, scale_name, transformed)
    return transformed, tick_info


def _build_tick_info(
    scale,
    scale_name: str,
    transformed: np.ndarray,
) -> tuple[list, list]:
    """Generate human-readable tick positions for a non-linear scale."""
    t_min = float(np.nanmin(transformed))
    t_max = float(np.nanmax(transformed))

    if scale_name == "log":
        # Decade ticks: 10^N for N covering the range
        raw_min = float(scale.inverse(t_min)) if not np.isnan(t_min) else 1
        raw_max = float(scale.inverse(t_max)) if not np.isnan(t_max) else 1e6
        raw_min = max(raw_min, 1e-3)
        raw_max = max(raw_max, raw_min * 10)
        low = int(np.floor(np.log10(raw_min)))
        high = int(np.ceil(np.log10(raw_max)))
        raw_ticks = [10 ** e for e in range(low, high + 1)]
        tickvals = [float(scale(v)) for v in raw_ticks if not np.isnan(scale(v))]
        ticktext = [_fmt_number(v) for v in raw_ticks]

    else:
        # logicle / hyperlog: use decade-like ticks in the linear region too
        # Try: -1000, -100, 0, 100, 1000, 10000, 100000, 1000000
        candidate_raw = [-1e6, -1e5, -1e4, -1e3, -1e2, 0,
                          1e2, 1e3, 1e4, 1e5, 1e6, 1e7]
        tickvals, ticktext = [], []
        for v in candidate_raw:
            try:
                tv = float(scale(v))
                if np.isfinite(tv) and t_min <= tv <= t_max:
                    tickvals.append(tv)
                    ticktext.append(_fmt_number(v))
            except Exception:
                pass

    return tickvals, ticktext


def _fmt_number(v: float) -> str:
    if v == 0:
        return "0"
    av = abs(v)
    if av >= 1e4:
        e = int(np.log10(av))
        m = v / (10 ** e)
        if abs(m - round(m)) < 0.01:
            return f"10<sup>{e}</sup>" if m > 0 else f"-10<sup>{e}</sup>"
        return f"{v:.2g}"
    if av < 0.01:
        return f"{v:.2g}"
    return str(int(v)) if v == int(v) else f"{v:.3g}"


def apply_scale_axes(fig, x_tick_info, y_tick_info=None):
    """Push tick overrides onto all axes of a figure dict in-place."""
    layout = fig.get("layout", {})

    def _patch_axis(axis_key: str, tick_info):
        if tick_info is None:
            return
        tickvals, ticktext = tick_info
        if not tickvals:
            return
        ax = layout.setdefault(axis_key, {})
        ax["tickvals"] = tickvals
        ax["ticktext"] = ticktext
        ax["tickmode"] = "array"

    # Patch every xaxis/yaxis found (handles faceted subplots too)
    for key in list(layout.keys()):
        if key.startswith("xaxis") and x_tick_info:
            _patch_axis(key, x_tick_info)
        if key.startswith("yaxis") and y_tick_info:
            _patch_axis(key, y_tick_info)

    # Also handle base xaxis/yaxis
    _patch_axis("xaxis", x_tick_info)
    if y_tick_info:
        _patch_axis("yaxis", y_tick_info)


# ── Faceting ──────────────────────────────────────────────────────────────────

def get_facet_groups(
    df: pd.DataFrame,
    xfacet: str | None,
    yfacet: str | None,
    huefacet: str | None,
) -> dict:
    """Return metadata needed for faceted subplot construction.

    Returns a dict with:
      row_vals, col_vals — sorted unique values for row/col facets
      hue_vals           — sorted unique values for hue facet
      n_rows, n_cols     — grid dimensions
    """
    from natsort import natsorted

    row_vals = natsorted(df[yfacet].unique().tolist()) if yfacet and yfacet in df.columns else [None]
    col_vals = natsorted(df[xfacet].unique().tolist()) if xfacet and xfacet in df.columns else [None]
    hue_vals = natsorted(df[huefacet].unique().tolist()) if huefacet and huefacet in df.columns else [None]

    return {
        "row_vals": row_vals,
        "col_vals": col_vals,
        "hue_vals": hue_vals,
        "n_rows": len(row_vals),
        "n_cols": len(col_vals),
    }


def subset_df(df: pd.DataFrame, row_val, col_val, row_key: str | None, col_key: str | None) -> pd.DataFrame:
    """Filter df to a single facet cell."""
    if row_key and row_val is not None:
        df = df[df[row_key] == row_val]
    if col_key and col_val is not None:
        df = df[df[col_key] == col_val]
    return df


# ── Placeholder figure ─────────────────────────────────────────────────────────

def placeholder_figure(message: str) -> dict:
    return {
        "data": [],
        "layout": {
            "annotations": [{
                "text": message,
                "xref": "paper", "yref": "paper",
                "x": 0.5, "y": 0.5,
                "showarrow": False,
                "font": {"size": 16, "color": "#888"},
            }],
            "xaxis": {"visible": False},
            "yaxis": {"visible": False},
            "plot_bgcolor": "#fafafa",
            "paper_bgcolor": "#fafafa",
        },
    }


# ── Shared layout defaults ─────────────────────────────────────────────────────

BASE_LAYOUT = {
    "plot_bgcolor": "#ffffff",
    "paper_bgcolor": "#ffffff",
    "margin": {"l": 70, "r": 20, "t": 50, "b": 70},
    "legend": {"orientation": "v"},
    "font": {"size": 12},
}
