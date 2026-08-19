# Cytoflow: PyQt → Dash/Plotly Migration Plan

Status: Proposal / Planning
Date: 2026-08-19

## Repository snapshot

| Layer | What exists today |
|---|---|
| Core library | `cytoflow/` — pure Python, no Qt dependency. `Experiment` (pandas DataFrame), ~25 `IOperation` classes, ~15 `IView` classes (matplotlib/seaborn) |
| GUI | `cytoflowgui/` — Envisage/Pyface Tasks app, TraitsUI forms, PyQt5 5.15 |
| Computation | Dual-process: `LocalWorkflow` (GUI process) ↔ `RemoteWorkflow` (worker process) via `multiprocessing.Pipe` |
| Plotting | matplotlib Agg renderer in the remote process, Agg buffer piped back to a QWidget in the local process |
| Serialization | YAML `.flow` files via `camel` library |
| Plugin count | 33 op plugins, 20 view plugins |

## Key insight: the core library is already headless

`cytoflow/` has zero Qt or GUI dependencies. Every `IOperation.apply()` / `IView.plot()` is callable from plain Python. This is the single biggest advantage — the entire computation stack can be reused without modification.

---

## Architecture Decision: Dash + FastAPI (separate back end)

**Recommendation: FastAPI back end + Dash front end**

Reasons for a dedicated FastAPI back end over an all-in-Dash architecture:

| Concern | All-in-Dash | FastAPI + Dash |
|---|---|---|
| Long-running computations (tSNE, GMM, SOM can take minutes) | Blocks Dash callback thread; requires `DiskcacheManager` hacks | Background workers (Celery / `asyncio.TaskGroup`) with WebSocket progress |
| Workflow state across browser refreshes | Complex `dcc.Store` serialization | Server-side session state; browser just renders |
| Future clients (Jupyter, CLI, scripting) | Impossible without extracting logic | REST API is immediately usable |
| Large data (millions of events) | Entire DataFrame must be serialized to/from browser | Only Plotly trace JSON is sent to browser; events capped at 500k via server-side sampling |
| Concurrency (multiple users / tabs) | Very difficult | Straightforward with FastAPI workers |
| Testing | Hard to unit-test callbacks | API endpoints are easily unit-tested |

The split also maps naturally onto the existing two-process model: the FastAPI server plays the role of `RemoteWorkflow`.

---

## Proposed Architecture

```
Browser (Dash SPA)
  │  HTTP/REST + WebSocket
  ▼
FastAPI server  ─── SessionManager (one WorkflowState per session)
  │                       │
  │                 AsyncWorker (asyncio + ProcessPoolExecutor)
  │                       │
  │               cytoflow/ core library (unchanged)
  │                       │
  │               PlotlyRenderer (new: replaces matplotlib views)
  │
  └── serves the Dash app as a sub-application (via WSGIMiddleware)
```

### Session model
Each browser session owns a `WorkflowState` object on the server:
```python
@dataclass
class WorkflowState:
    workflow: list[WorkflowItem]   # the pipeline
    current_item: int              # selected step index
    experiment_cache: dict[int, Experiment]  # results keyed by step index
    status: dict[int, StepStatus]  # invalid/estimating/applying/valid
```

Sessions identified by a UUID stored in a `dcc.Store` or cookie. On reconnect the state is restored from the server (no serialization to the browser for heavy data).

---

## Component Inventory: What maps where

### A. Things that require NO changes (keep as-is)

| Component | Path | Notes |
|---|---|---|
| `Experiment` model | `cytoflow/experiment.py` | Pure Python/pandas |
| All `IOperation` classes | `cytoflow/operations/*.py` | `estimate()` and `apply()` unchanged |
| FCS parser | `fcsparser/` submodule | Used inside `ImportOp` |
| Logicle C++ extension | `cytoflow/utility/logicle_ext/` | Scale math unchanged |
| Scale infrastructure | `cytoflow/utility/scale.py` | Used to pre-transform axes |
| Workflow serialization | `cytoflowgui/workflow/serialization.py` | Keep `.flow` YAML format; expose via API |
| Jupyter export | `flow_task.py:on_notebook()` + `get_notebook_code()` | Expose as API endpoint |

### B. Things that map directly to Dash/Plotly (moderate effort)

| Qt/Traits component | Dash/Plotly equivalent |
|---|---|
| `WorkflowDockPane` (left sidebar, pipeline list) | `dash-bootstrap-components` `Accordion` or custom sidebar with per-step cards |
| Operation toolbar (add/remove step buttons) | `dbc.ButtonGroup` in the sidebar header |
| `ViewDockPane` (right panel, view selector) | `dbc.Tabs` for view type; form below |
| `PlotParamsPane` (plot parameters) | Collapsible `dbc.Collapse` section within the view panel |
| `ExperimentBrowserDockPane` | `dash_table.DataTable` showing channels/conditions/statistics |
| `HelpDockPane` (HTML help) | `dbc.Offcanvas` or modal; HTML already exists in `cytoflowgui/help/` |
| `FlowTaskPane` (central canvas) | `dcc.Graph` with `plotly.graph_objects.Figure` |
| File open/save dialogs | `dcc.Upload` for FCS files; save as API call; load `.flow` via upload or server-path input |
| `VerticalNotebookEditor` (accordion pipeline list) | `dbc.Accordion` with one item per step |
| `SubsetListEditor` | Multi-select `dcc.Dropdown` + range sliders |
| `RangeSlider` editor | `dcc.RangeSlider` |
| `ExtEnumEditor` | `dcc.Dropdown` |
| `ColorTextEditor` | `dcc.Input` + color swatch (or `dbc.Input` with color type) |
| Operation status badges (valid/estimating/error) | `dbc.Badge` with color |
| Preferences dialog | Settings page / `dbc.Modal` |
| Export dialog (`ExportTask`) | Download button → `dcc.Download` |

### C. Views: Matplotlib → Plotly (most translation work)

Each view in `cytoflow/views/` uses matplotlib + seaborn. Translations:

| Current view | Plotly approach | Complexity |
|---|---|---|
| `HistogramView` | `go.Histogram` or pre-binned `go.Bar` | Low |
| `ScatterplotView` | `go.Scattergl` (WebGL); server samples to ≤500k events before sending | Low |
| `Histogram2DView` | `go.Histogram2dContour` + `go.Histogram2d` | Low-Medium |
| `KDE1DView` | Pre-compute KDE (scipy), render as `go.Scatter` filled area | Medium |
| `KDE2DView` | Pre-compute KDE grid (scipy), render as `go.Contour` | Medium |
| `DensityView` | Pre-bin server-side (`np.histogram2d`), render as `go.Heatmap` | Medium |
| `ViolinView` | `go.Violin` | Low |
| `BarChartView` | `go.Bar` | Low |
| `Stats1DView` | `go.Scatter` with error bars | Low |
| `Stats2DView` | `go.Scatter` x/y error bars | Low |
| `ParallelCoordsView` | `go.Parcoords` | Low |
| `RadvizView` | Custom `go.Scatter` (unit circle + spokes) | Medium |
| `TableView` | `dash_table.DataTable` | Low |
| `LongTableView` | `dash_table.DataTable` | Low |
| `MatrixView` | `go.Heatmap` | Low |
| `MSTView` | `go.Scatter` (nodes) + `go.Scatter` (edges) or `cytoscape` | Medium |

**Strategy for view layer**: Rather than gutting `cytoflow/views/`, add a parallel `cytoflow/views/plotly/` package. Each class has a `to_plotly(experiment, **kwargs) -> go.Figure` method. The matplotlib views remain for backward compatibility and Jupyter use.

### D. Custom scale axes (Logicle / Hyperlog) — requires workaround

Plotly does not support custom axis scales. The solution is to **pre-transform data** before passing it to Plotly, and then **fake the tick labels**:

```python
# In PlotlyRenderer:
scale = scale_factory("logicle", experiment, channel="FITC-A")
transformed = scale(data["FITC-A"])
tick_vals = scale.inverse(np.linspace(transformed.min(), transformed.max(), 8))
tick_text = [f"{v:.0f}" for v in tick_vals]
fig.update_xaxes(tickvals=np.linspace(...), ticktext=tick_text)
```

This is the same pattern used by the existing matplotlib backend (`CytoflowScaleFormatter`). The logicle C++ extension is unchanged; only the axis labeling layer changes.

### E. Interactive gating — Plotly-native mechanisms

The current GUI lets users draw gates interactively:
- `ThresholdOp`: click on histogram to set threshold
- `RangeOp`: drag two vertical lines on histogram
- `Range2DOp` / `QuadOp`: drag a rectangle on a scatterplot
- `PolygonOp`: draw an arbitrary closed shape on a scatterplot

Plotly supports `selectedData` and `relayoutData` callbacks. For non-rectangular gates, **lasso selection** (`dragmode='lasso'`) replaces the polygon vertex-clicking approach — it is natively supported in Plotly with no custom component required.

| Gate type | Plotly/Dash mechanism | Notes |
|---|---|---|
| Threshold (1 vertical line) | `dcc.Graph` `clickData` callback → numeric input; line rendered as `go.layout.Shape` | Single click |
| Range (two vertical lines) | `dcc.RangeSlider` below the plot, **or** Plotly `dragmode='select'` + `selectedData.range.x` | Either UX works |
| Rectangle (2D range / quad) | Plotly `dragmode='select'` → box-select → `selectedData.range` | Built-in Plotly |
| **Non-rectangular gate (replaces PolygonOp)** | Plotly **`dragmode='lasso'`** → `selectedData.lassoPoints.{x,y}` → compute convex hull or use raw lasso path | **No custom component needed** |

**How lasso gating works end-to-end:**

```python
# Dash callback triggered by dcc.Graph selectedData
@app.callback(Output("gate-coords", "data"), Input("scatter-plot", "selectedData"))
def capture_lasso(selected):
    if selected and "lassoPoints" in selected:
        xs = selected["lassoPoints"]["x"]
        ys = selected["lassoPoints"]["y"]
        # xs/ys are already in pre-transformed (scale) space;
        # apply inverse scale transform before storing as gate vertices
        real_xs = scale_x.inverse(np.array(xs))
        real_ys = scale_y.inverse(np.array(ys))
        return {"x": real_xs.tolist(), "y": real_ys.tolist()}
```

The lasso path coordinates are passed to `PolygonOp` (which already accepts an arbitrary vertex list) unchanged — the op itself does not need modification. Gate outlines are rendered back as a closed `go.layout.Shape` of type `"path"`.

**Trade-off vs. click-to-place polygon**: lasso selection is a continuous freehand drag rather than discrete vertex placement. This is generally easier for users and requires no custom UI code, at the cost of very precise control over individual vertices. A "refine gate" numeric table (editable vertex list) can be offered as an optional detail panel.

### F. Event sampling cap — 500k events per plot

All Plotly views enforce a server-side maximum of **500,000 events per rendered figure**. When the experiment exceeds this, the worker samples randomly (stratified by condition if faceting is active) before building the Plotly trace. The full unsampled dataset is always used for `IOperation.apply()` and `IOperation.estimate()` — sampling only affects the visual representation.

```python
MAX_PLOT_EVENTS = 500_000

def sample_for_plot(df: pd.DataFrame, condition_cols: list[str]) -> pd.DataFrame:
    if len(df) <= MAX_PLOT_EVENTS:
        return df
    if condition_cols:
        # Stratified sample: preserve proportions across conditions
        return df.groupby(condition_cols, group_keys=False).apply(
            lambda g: g.sample(frac=MAX_PLOT_EVENTS / len(df), random_state=0)
        )
    return df.sample(n=MAX_PLOT_EVENTS, random_state=0)
```

The rendered figure carries an annotation indicating the sample fraction (e.g., *"Showing 500k of 2.4M events (21%)"*) so users are always aware. This annotation is shown as a Plotly figure annotation at the bottom-right of the plot.

**Implications per view type:**

| View | Sampling effect | Notes |
|---|---|---|
| Scatterplot | Density visually lower; gates still drawn from full data | Low impact |
| Histogram | Pre-bin server-side from full dataset before sampling; use `go.Bar` not `go.Histogram` | No impact — bins computed from full data |
| KDE | Compute KDE from full dataset; only send curve points to browser | No impact |
| Stats views | Statistics always computed from full data by `ChannelStatisticOp` | No impact |
| Density | Pre-bin (`np.histogram2d`) from full data; send heatmap counts | No impact |

### G. Real-time progress — WebSocket via FastAPI

Long operations (tSNE, SOM, Gaussian mixture estimate) need live status:

```
FastAPI WebSocket /ws/{session_id}
  ← {"type": "status", "step": 3, "state": "estimating", "progress": 0.42}
  ← {"type": "plot_ready", "step": 3}
  ← {"type": "error", "step": 3, "message": "..."}
```

On the Dash side, use `dash-extensions`'s `WebSocket` component or a `dcc.Interval` polling the status endpoint (simpler, slightly less responsive).

---

## New Package Structure

```
cytoflow/                        (unchanged — core library)
cytoflowgui/                     (keep for now; deprecate over time)
cytoflowweb/                     (new)
├── api/
│   ├── main.py                  # FastAPI app + Dash mount
│   ├── routers/
│   │   ├── sessions.py          # POST /sessions, DELETE /sessions/{id}
│   │   ├── workflow.py          # GET/POST/DELETE /sessions/{id}/workflow
│   │   ├── operations.py        # POST …/steps, PUT …/steps/{n}/params
│   │   ├── views.py             # GET …/steps/{n}/plot (returns Plotly JSON)
│   │   ├── files.py             # POST /upload/fcs, GET /files
│   │   └── export.py            # GET …/export/notebook, GET …/export/fcs
│   ├── workers/
│   │   ├── executor.py          # ProcessPoolExecutor / Celery task runner
│   │   └── tasks.py             # apply_step(), estimate_step(), plot_step()
│   ├── session_manager.py       # In-memory or Redis-backed session store
│   └── ws.py                    # WebSocket progress broadcaster
├── dash_app/
│   ├── app.py                   # Dash app factory; mounted at /
│   ├── layout/
│   │   ├── main.py              # Top-level layout: sidebar + canvas + right panel
│   │   ├── sidebar.py           # Pipeline accordion
│   │   ├── canvas.py            # dcc.Graph central pane
│   │   └── right_panel.py       # View selector + params
│   ├── callbacks/
│   │   ├── workflow.py          # Add/remove/reorder steps
│   │   ├── parameters.py        # Op param changes → API calls
│   │   ├── plot.py              # Fetch and display plots
│   │   └── websocket.py         # Handle real-time status messages
│   └── components/
│       ├── op_forms/            # Per-operation parameter form components
│       │   ├── base.py
│       │   ├── threshold.py
│       │   ├── lasso.py         # lasso gate drawing via dragmode='lasso'
│       │   └── ... (33 total)
│       └── view_forms/          # Per-view parameter form components
│           ├── base.py
│           └── ... (20 total)
└── views/plotly/                # New Plotly renderers (parallel to cytoflow/views/)
    ├── base.py
    ├── histogram.py
    ├── scatterplot.py
    └── ... (15 total)
```

---

## Required Additional Packages

| Package | Purpose | Notes |
|---|---|---|
| `fastapi` | Back-end API server | + `uvicorn` for serving |
| `dash` ≥ 2.17 | Browser UI framework | |
| `dash-bootstrap-components` | Layout, accordion, badges | `dbc` |
| `plotly` ≥ 5.20 | Interactive charts | Already installable alongside matplotlib |
| `dash-extensions` | WebSocket component, `ServersideOutput` | Or use `dcc.Interval` polling instead |
| `celery` + `redis` | Task queue for long computations | Optional; `ProcessPoolExecutor` sufficient for single-user deployment |
| `httpx` or `requests` | Dash → FastAPI calls (server-side) | Or mount Dash inside FastAPI and call functions directly |

> **Datashader is not required for the initial product.** With the 500k event cap enforced server-side, `go.Scattergl` handles all scatter views acceptably. `np.histogram2d` covers the density view. Datashader remains an optional future enhancement for zooming into very high-density regions without resampling.

---

## Migration Phases

### Phase 1 — Foundation (2–3 weeks)
1. Create `cytoflowweb/` package skeleton
2. Implement `SessionManager` and `WorkflowState`
3. FastAPI routers: sessions, workflow CRUD, file upload
4. Worker: `apply_step()` and `plot_step()` using existing `IOperation.apply()`
5. Basic Dash shell: top-level layout, sidebar placeholder, `dcc.Graph` canvas
6. Wire Dash ↔ FastAPI via REST (no WebSocket yet)
7. Milestone: Import FCS files, run `ImportOp`, display a histogram

### Phase 2 — View Layer (3–4 weeks)
8. Implement `cytoflowweb/views/plotly/` for all 15 view types
9. Implement custom scale axis tick generation (logicle, hyperlog, log)
10. Wire plot callbacks: step selection → fetch plot JSON → `dcc.Graph.figure`
11. Implement faceting (per-facet subplots via `make_subplots`)
12. Implement `PlotParamsPane` equivalent in right panel
13. Milestone: All 15 view types render correctly with correct axis scales

### Phase 3 — Operation Forms (3–4 weeks)
14. Create base `OpForm` Dash component pattern
15. Implement parameter forms for all 33 operations
16. Wire form changes → API `PUT /steps/{n}/params` → re-apply → re-plot
17. Implement `SubsetListEditor` equivalent (channel range + category filters)
18. Milestone: Full pipeline creation and editing without interactive gating

### Phase 4 — Interactive Gating (2–3 weeks)
19. Implement threshold gate: `dcc.Graph` `clickData` → threshold line `go.layout.Shape`
20. Implement range gate: `dcc.RangeSlider` or Plotly box-select `selectedData.range.x`
21. Implement 2D range / quad gates: Plotly `dragmode='select'` → `selectedData.range`
22. Implement lasso gate: Plotly `dragmode='lasso'` → `selectedData.lassoPoints` → inverse-scale transform → `PolygonOp` vertices
23. Add gate overlay rendering: closed `go.layout.Shape` path drawn over the plot after gate is committed
24. Milestone: All gate types work end-to-end; lasso gate commits on mouseup and re-runs the pipeline

### Phase 5 — Real-time Progress & UX (1–2 weeks)
25. Add FastAPI WebSocket endpoint
26. Integrate `dash-extensions` WebSocket client
27. Status badges per pipeline step (valid / estimating / applying / error)
28. Cancel running computation button
29. Milestone: tSNE and SOM show live progress

### Phase 6 — File I/O & Export (1 week)
30. `dcc.Upload` for FCS files and `.flow` workflow files
31. Save / load workflow via API (keep YAML `.flow` format)
32. Export notebook (`nbformat`) via `dcc.Download`
33. Export FCS (`ExportFCS` view) via `dcc.Download`
34. Milestone: Round-trip save/load of a workflow

### Phase 7 — Polish & Parity (2 weeks)
35. Help drawer (reuse existing HTML from `cytoflowgui/help/`)
36. Experiment browser pane (`dash_table.DataTable` for channels/conditions)
37. Preferences (color palettes, default scales)
38. Keyboard shortcuts via `dcc.Keyboard`
39. Responsive layout adjustments
40. Milestone: Feature parity with Qt GUI

---

## Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| Logicle scale tick labels look wrong | Medium | Pre-transform + fake ticks; test against existing matplotlib output |
| Lasso gate inverse-scale transform introduces coordinate error | Low | Lasso coords are in transformed space; apply `scale.inverse()` before storing; add integration test vs. existing `PolygonOp` |
| Sampled scatter plot misleads user about event density | Medium | Always show sample-fraction annotation on plot; sampling is stratified by condition; full data used for all computations |
| Histogram bins differ from full-data bins if binning is event-count-dependent | Low | Bin histograms server-side from full dataset before sampling; send `go.Bar` (pre-binned) not `go.Histogram` |
| Large FCS files (>50MB) slow to upload | Medium | Stream FCS parse; store server-side, only send metadata to browser |
| Session state memory usage (multiple experiments in RAM) | Medium | LRU cache on `WorkflowState`; evict stale sessions; optional Redis/disk persistence |
| Traits/TraitsUI changes during migration break existing `.flow` files | Low | API layer reads existing `.flow` files using the existing `camel` deserializer from `cytoflowgui` |
| Faceted plots (many subplots) are slow in Plotly | Medium | Apply 500k cap per facet (not total); pre-bin heavy views; `make_subplots` with shared axes |

---

## What to keep from `cytoflowgui/`

- `workflow/serialization.py` — the `.flow` YAML read/write logic
- `workflow/workflow_item.py` — `WorkflowItem` data structure (strip Qt event wiring)
- All `op_plugins/*.py` — parameter metadata (trait `apply`/`estimate` tags) can drive auto-form generation
- All `get_notebook_code()` implementations — export feature
- `help/` HTML files — reuse in the help drawer
- The `Tube`, `ImportOp`, and condition-building logic

Everything in `cytoflowgui/` that touches `pyface`, `envisage`, `traitsui.api.View`, or `pyface.qt` can eventually be discarded.
