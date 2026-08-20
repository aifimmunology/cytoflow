"""
cytoflowweb.views.plotly
------------------------

Plotly renderers for all cytoflow view types.

Importing this package registers every renderer in
``cytoflowweb.views.plotly.base.VIEW_REGISTRY``.
"""

# Import each module so the @register decorators execute
from . import (  # noqa: F401
    histogram,
    scatterplot,
    histogram_2d,
    kde_1d,
    kde_2d,
    densityplot,
    violin,
    bar_chart,
    stats_1d,
    stats_2d,
    parallel_coords,
    radviz,
    table,
    matrix,
    mst,
)

from .base import VIEW_REGISTRY  # noqa: F401
