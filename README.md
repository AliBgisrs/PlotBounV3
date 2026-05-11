# Plot Boundary V3

**Fast, offline plot-boundary delineation for large orthomosaics.**

A native Windows desktop application for generating field-trial plot boundaries on UAV/satellite orthomosaics. Built as the successor to [PlotBounV2](https://github.com/AliBgisrs/PlotBounV2) (Streamlit web app), Plot Boundary V3 handles multi-gigabyte rasters locally with pan/zoom that stays responsive at any zoom level, supports meter-based input alongside pixels, and exports to GeoJSON, ESRI Shapefile, GeoPackage, and File Geodatabase.

![Grid rendered on orthomosaic](docs/screenshots/grid-rendered.png)

---

## Table of Contents
- [Why this exists](#why-this-exists)
- [Features](#features)
- [Screenshots](#screenshots)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [User Guide](#user-guide)
  - [1. Field Setup](#1-field-setup)
  - [2. Trials & Labels](#2-trials--labels)
  - [3. Geometry](#3-geometry)
  - [4. Plot Group Editor](#4-plot-group-editor)
  - [5. Colors & Display](#5-colors--display)
- [Working with Large Orthomosaics](#working-with-large-orthomosaics)
- [Export Formats](#export-formats)
- [Coordinate Reference Systems & Units](#coordinate-reference-systems--units)
- [Keyboard & Mouse Reference](#keyboard--mouse-reference)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Troubleshooting](#troubleshooting)
- [Credits](#credits)

---

## Why this exists

PlotBounV2 (the Streamlit web ancestor) loads the entire orthomosaic into memory with PIL before showing anything. For a 10 GB GeoTIFF that's not viable — the browser stalls, the kernel pages to disk, or RAM runs out. Plot Boundary V3 solves this by:

- Opening the raster with **rasterio** in lazy mode, never loading it all at once.
- Reading only the **visible viewport** at the **screen's resolution** on every pan/zoom (debounced 120 ms).
- Building **internal overviews** (image pyramids) once, on first open, so zoomed-out views are instant.

The result: a 30 000 × 40 000 px five-band orthomosaic pans and zooms as smoothly as a 2 000 × 2 000 px JPEG.

## Features

### Viewing
- Open GeoTIFF, JP2, PNG, and JPEG orthomosaics
- Pan with mouse drag, zoom with mouse wheel
- Automatic image pyramid (overview) building on first open
- 2nd/98th-percentile auto-contrast for uint16 and float rasters
- Multi-band rasters: defaults to bands 1/2/3 for RGB display (configurable in M2)

### Grid generation
- Parametric plot grid: rows × columns × multiple trials, all configurable in real time
- Pixel **or** meter input units (meters auto-enabled on projected metric CRS)
- Straight or serpentine plot numbering
- Horizontal growth East/West, vertical growth North/South
- Independent gaps for E-W, N-S, and between-trials
- Grid rotation in degrees with 0.01° precision

### Plot Group Editor (column-range editing)
- Pick a **Start ID** and **End ID**; the tool finds their columns and edits every column in between
- Per-strip X/Y shift to nudge misaligned rows or columns
- Per-strip rotation delta that **adds to** the main grid rotation
- Selected plots highlighted in a distinct color so corrections are obvious

### Origin control
- Click anywhere on the map to set the grid origin
- **Lock the origin** to prevent accidental clicks from moving it (toggle in sidebar)
- Origin marker (cosmetic crosshair) stays at constant screen size at all zoom levels

### Style customization
- User-pickable colors for: normal polygons, edited polygons, labels, origin marker
- Polygon line width in screen pixels (cosmetic — stays crisp at any zoom)
- Label font size in screen pixels (stays readable at any zoom)
- All style changes apply live; no regenerate needed

### Export
- GeoJSON (always available)
- ESRI Shapefile (via fiona / GDAL)
- GeoPackage (via fiona / GDAL — recommended portable format)
- File Geodatabase (requires GDAL ≥ 3.6)

All exports include `ID` and `Trial` attributes and use the orthomosaic's source CRS when available.

## Screenshots

### Sidebar — configuration panel
| Top half | Bottom half |
|---|---|
| ![Sidebar — Field Setup, Trials, Geometry](docs/screenshots/sidebar-top.png) | ![Sidebar — Plot Group Editor, Colors](docs/screenshots/sidebar-bottom.png) |

### Live rendering on an orthomosaic
The grid regenerates instantly as you adjust any parameter:

![Grid rendered on orthomosaic with plot IDs](docs/screenshots/grid-rendered.png)

### Locked origin in meter units
When the orthomosaic has a projected metric CRS, dimensions can be entered in meters and the origin readout is also shown in meters. The lock button prevents accidental origin moves:

![Field Setup with locked origin in meters](docs/screenshots/origin-locked.png)

---

## Requirements

- **OS:** Windows 10 / 11 (64-bit)
- **Python:** 3.10 or later (only needed when running from source)
- **RAM:** 4 GB minimum, 8 GB+ recommended for orthomosaics over 5 GB
- **Disk:** ~250 MB for the virtual environment (or the unpacked EXE)

The tool is CPU-only — no GPU required.

## Installation

### Option A — Run from source (recommended during development)

```cmd
git clone <your-repo-url> PlotBoundaryV3
cd PlotBoundaryV3
run_dev.bat
```

On first launch, `run_dev.bat` creates a `.venv\` virtual environment and installs all dependencies from `requirements.txt` (~2 minutes, ~200 MB download). Subsequent launches take ~3 seconds.

Dependencies (pinned in `requirements.txt`):

| Package | Purpose |
|---|---|
| `PySide6` | Qt-based desktop UI |
| `rasterio` | Windowed raster reads + overviews; bundles GDAL |
| `numpy` | Array math for raster windows |
| `Pillow` | Image format support |
| `shapely` | Polygon geometry helpers |
| `fiona` | Shapefile / GeoPackage / GDB writers |
| `pyproj` | CRS conversions |

### Option B — Run the packaged EXE

A single-folder PyInstaller distribution is on the roadmap (M6). Once available, end users can simply unzip and run `PlotBoundaryV3.exe` with no Python installation.

## Quick Start

1. **Launch the app**
   ```cmd
   run_dev.bat
   ```

2. **Open an orthomosaic** — `File → Open Orthomosaic…` and pick a TIFF/JP2/PNG/JPEG.
   - If the file lacks overviews, the app asks once whether to build them. Click **Yes** for fast pan/zoom (recommended).

3. **Set the origin** — left-click anywhere on the map. The cyan crosshair marks the origin. The grid is generated immediately.

4. **Adjust geometry** — change Rows per Trial, Total Columns, Plot Width/Height, gaps, rotation. The grid updates as you type.

5. **Lock the origin** — once the origin is right, click the **Unlocked** button so accidental clicks don't move it.

6. **Export** — `File → Export → GeoJSON / Shapefile / GeoPackage / File Geodatabase`. Pick a path and you're done.

---

## User Guide

The sidebar on the left is organized into five sections.

### 1. Field Setup

| Control | What it does |
|---|---|
| **Origin** | Read-only display of the current origin in the selected unit. Set by left-clicking the map (when unlocked). |
| **Lock button** | When **Locked**, clicks on the map are ignored. Toggle to allow re-setting the origin. |
| **Horizontal Growth** | Direction in which plot **columns** extend from the origin (East = right; West = left). |
| **Vertical Growth** | Direction in which plot **rows** extend from the origin (South = down; North = up). |
| **Input Units** | `Pixels` always available. `Meters` enabled only on rasters with a projected CRS in metric units. Switching units re-displays all dimensional fields in the new unit; values are preserved. |

### 2. Trials & Labels

| Control | What it does |
|---|---|
| **Number of Trials** | How many independent trial blocks to stack vertically. Each trial is separated by **Trial Gap**. |
| **Trial N Start ID** | The plot ID assigned to the first plot of trial N. Subsequent plots are numbered sequentially. |
| **Labeling Order** | `Straight` numbers each row left-to-right. `Serpentine` reverses every other row (boustrophedon). |

### 3. Geometry

| Control | What it does |
|---|---|
| **Rows per Trial** | Plots tall per trial block. |
| **Total Columns** | Plots wide. |
| **Plot Width / Height** | Plot dimensions in the selected unit. |
| **E-W Gap** | Horizontal spacing between adjacent plot columns. |
| **N-S Gap** | Vertical spacing between adjacent plot rows within a trial. |
| **Trial Gap** | Vertical spacing between trials (added to the last N-S gap of the previous trial). |
| **Grid Rotation** | Rotates the entire grid around the origin, in degrees. Sub-degree precision. |

### 4. Plot Group Editor

Used to nudge a contiguous strip of columns when the orthomosaic isn't perfectly aligned with the underlying grid.

| Control | What it does |
|---|---|
| **Enabled checkbox** (group title) | Switch the editor on/off. When off, no plots are edited regardless of other values. |
| **Start ID / End ID** | The tool finds the **column** of each ID and edits **every column in the range** between them (inclusive). Order doesn't matter — End < Start works the same way. Invalid IDs (not in the grid) are ignored. |
| **Shift X / Shift Y** | Translate every plot in the selected columns by this offset, in the selected unit. |
| **Strip Rotation Δ** | Additional rotation applied to selected plots **on top of** the main Grid Rotation. So `Grid = 30°` + `Δ = 5°` → those plots are at 35°. |

Selected plots are drawn in the **Edited Polygon Color** (yellow by default) so corrections are visible.

> **Example.** A 5×5 grid numbered 100-124, Start = 102, End = 108. ID 102 lives in column 2; ID 108 lives in column 3. The editor selects **all 10 plots in columns 2 and 3** — rows 0 through 4 in those two columns. It does **not** select any plot in columns 0, 1, or 4.

### 5. Colors & Display

| Control | What it does |
|---|---|
| **Polygon Color** | Outline color for normal (un-edited) plots. |
| **Edited Polygon Color** | Outline color for plots inside the Plot Group Editor range. |
| **Label Color** | Color of the plot-ID text drawn at each plot's center. |
| **Origin Marker Color** | Color of the crosshair drawn at the origin. |
| **Polygon Width (px)** | Outline thickness in **screen pixels** — stays crisp at any zoom. |
| **Label Size (px)** | Label font size in **screen pixels** — stays readable as you zoom in and out. |

All five color buttons open a standard color picker. Changes are live — no regenerate needed.

---

## Working with Large Orthomosaics

### Overviews (image pyramids)

For fast pan/zoom on multi-gigabyte rasters, the tool relies on **internal overviews**: pre-computed downsampled copies of the image embedded in the same file. When you zoom out, rasterio reads from a small overview level instead of the full resolution data.

**On first open**, the app checks `dataset.overviews(1)`. If the file has no overviews and the larger dimension exceeds 4 000 px, you're prompted to build them. Click **Yes** (default). The build:

- runs on a background thread (UI stays responsive)
- adds overviews at decimation factors **2, 4, 8, 16, 32, 64**
- uses **average** resampling (good for smooth radiometry)
- writes inside the file (~5-10% size increase; no pixel data is lost)
- takes seconds to a few minutes depending on file size and disk speed

If you decline, the app still works but zooming out will be slow (full-resolution reads + on-the-fly downsampling).

> **Note:** Internal overviews modify the source file. If your orthomosaic lives on read-only media, copy it locally first. External `.ovr` sidecar overviews are planned for a future release.

### Viewport-only rendering

On every pan or zoom event:

1. The visible scene rectangle is mapped back to image pixel coordinates.
2. Only that window is read from rasterio — never the whole file.
3. The output resolution matches the viewport's pixel size (never up-sampled past viewport), so memory use is constant.
4. The redraw is debounced 120 ms so dragging is smooth.

This is why opening a 30 GB orthomosaic is just as fast as opening a 30 MB one.

### Auto-contrast for non-8-bit rasters

uint16 and float rasters are stretched to 8-bit per band using **2nd and 98th percentiles** computed from a 1024-px-max downsample at open time. This gives consistent contrast across pans without flicker.

---

## Export Formats

`File → Export →` opens a save dialog for the selected format. All exports include:

- One feature per plot
- Geometry as `Polygon` with a closed ring (last point equals first)
- Properties: `ID` (integer plot ID) and `Trial` (1-based trial number)
- CRS from the source raster (when present)

| Format | Driver | Extension | Notes |
|---|---|---|---|
| GeoJSON | built-in JSON | `.geojson` | Always available; pretty-printed |
| ESRI Shapefile | `fiona` + `ESRI Shapefile` | `.shp` (plus `.dbf`, `.shx`, `.prj`) | Field name length limited to 10 chars |
| GeoPackage | `fiona` + `GPKG` | `.gpkg` | **Recommended** — single-file, open standard, no length limits |
| File Geodatabase | `fiona` + `OpenFileGDB` | `.gdb` (directory) | **Requires GDAL ≥ 3.6.** Errors are surfaced clearly if write support is unavailable. |

---

## Coordinate Reference Systems & Units

### Meter mode availability

The **Meters** option appears in the Input Units dropdown only when **all** of the following are true:

1. The orthomosaic has a CRS embedded.
2. The CRS is **projected** (not geographic / lat-lon).
3. The CRS uses **metric** linear units (metre / meter).

Examples:

| CRS | Meter mode? |
|---|---|
| EPSG:32633 (UTM 33N) | ✅ Yes |
| EPSG:3857 (Web Mercator) | ✅ Yes |
| EPSG:4326 (WGS84 lat-lon) | ❌ No (geographic) |
| ESRI:102008 (Albers, feet) | ❌ No (non-metric) |
| (no CRS / PNG / JPEG) | ❌ No |

When meter mode is disabled, all dimensional fields stay in pixels. The conversion factor used internally is `px_per_meter = 1 / abs(transform.a)` for the X axis and `1 / abs(transform.e)` for the Y axis.

### Reprojection

The tool does **not** reproject your orthomosaic. Output features use the raster's native CRS. If you need a different CRS, reproject the orthomosaic before opening, or reproject the exported file in QGIS / `ogr2ogr`.

---

## Keyboard & Mouse Reference

| Action | Binding |
|---|---|
| Open orthomosaic | `Ctrl + O` |
| Fit image to view | `Ctrl + 0` |
| Quit | `Ctrl + Q` |
| Pan | Left-mouse drag (when origin is **locked**) |
| Set origin | Left-click (when origin is **unlocked**) |
| Zoom | Mouse wheel (zooms around the cursor) |

> **Tip:** Lock the origin (button in the Field Setup section) before panning, so a stray click doesn't move the grid.

---

## Project Structure

```
PlotBoundaryV3/
├── plotbounv3/
│   ├── __main__.py          Application entry point
│   ├── main_window.py       QMainWindow, menus, signal wiring
│   ├── style.py             PlotStyle dataclass (colors & sizes)
│   ├── grid/
│   │   └── generator.py     rotate_point + parametric grid + column-range editor
│   ├── raster/
│   │   ├── source.py        RasterSource — windowed reads, auto-contrast
│   │   └── overviews.py     Detect / build internal overviews
│   ├── canvas/
│   │   ├── map_view.py      QGraphicsView with debounced viewport rendering
│   │   └── plot_layer.py    Polygon + label items, cosmetic pens, screen-pixel fonts
│   ├── widgets/
│   │   ├── sidebar.py       The configuration panel
│   │   └── color_button.py  Color-swatch button opening QColorDialog
│   └── io/
│       └── export.py        GeoJSON / Shapefile / GeoPackage / GDB writers
├── tests/
│   └── test_generator.py    Golden-output tests vs. app.py + column-range tests
├── docs/
│   └── screenshots/         README screenshots
├── requirements.txt
├── run_dev.bat              First-run venv + dependency install + launch
├── run_tests.bat            Run the test suite
└── .gitignore
```

## Testing

```cmd
run_tests.bat
```

Or manually:

```cmd
.venv\Scripts\activate
python -m tests.test_generator
```

The test suite covers:

- **Core grid math parity** against the original `app.py` (5 tests): basic straight, serpentine, rotated, growth-direction-flipped, multi-trial.
- **Column-range Plot Group Editor** (8 tests): basic range, single-column, reversed Start/End, no bleed to unrelated columns, serpentine physical-column lookup, rotation delta, disabled = no edits, invalid IDs = no edits.

All 13 tests must pass before merging changes to the generator.

## Roadmap

The project is being built in shippable milestones. Each milestone is functional on its own.

| Milestone | Status | What |
|---|---|---|
| **M1** | ✅ Done | Qt window, rasterio windowed reads, overviews, ported grid generator, GeoJSON export |
| **M1.5** | ✅ Done | Color customization, multi-format export, origin lock, unit selection (px/m), dynamic label size, column-range Plot Group Editor |
| **M2** | ⏳ Next | Save/load project (`.pbproj` JSON: image path + all params + per-plot overrides) |
| **M3** | ⏳ Planned | Polygon edit mode — drag plot, rotate, delete, undo/redo |
| **M4** | ⏳ Planned | Vegetation-index auto-snap (ExG / NDVI / NDRE) — snap polygon edges to vegetation mask |
| **M5** | ⏳ Planned | Batch processing — apply same config to N orthomosaics, write outputs to a folder |
| **M6** | ⏳ Planned | PyInstaller single-folder build — distribute as `PlotBoundaryV3.exe` |

## Troubleshooting

### "Building overviews..." dialog hangs

Overview building writes inside the source file. If the file is on a network drive, on read-only media, or open in another application (QGIS / ArcGIS), the write will fail. Close the file in other apps and try again, or click **No** at the prompt to skip overview building (zoom will be slow but everything else works).

### Meter mode is greyed out

The orthomosaic must have a **projected metric** CRS. See the [CRS table above](#meter-mode-availability). If your file lacks a CRS, georeference it in QGIS first, or work in pixels.

### Export to File Geodatabase fails

The OpenFileGDB writer requires **GDAL 3.6 or later**. Check your GDAL version with:

```cmd
.venv\Scripts\activate
python -c "import rasterio; print(rasterio.__gdal_version__)"
```

If older, either upgrade `rasterio` (`pip install -U rasterio`), or export to **GeoPackage** instead — it's a single file, an open standard, and works everywhere ArcGIS and QGIS work.

### Labels disappear when zoomed way out

Labels are drawn at constant screen size (default 12 px). When the entire image is much larger than the viewport, plot centers may end up at the same screen pixel — labels overlap and become unreadable. Either zoom in, or increase the label size in **Colors & Display**.

### The grid rotates around the wrong point

The rotation pivot is always the **origin** (cyan crosshair). To rotate around a different point, click that point on the map to re-set the origin (after unlocking), then dial in the rotation.

### Polygon edges are jaggy

The polygon pen is **cosmetic** — it's drawn at the configured pixel width in screen space, regardless of zoom. This is intentional so lines stay readable at any zoom. If you want hairline edges, set Polygon Width to 1.

---

## Credits

**Developed by Ali Bazrafkan**

Built on:
- [PySide6](https://wiki.qt.io/Qt_for_Python) — Qt for Python (LGPL)
- [rasterio](https://rasterio.readthedocs.io/) — Pythonic geospatial raster I/O (BSD)
- [fiona](https://fiona.readthedocs.io/) — vector I/O (BSD)
- [GDAL](https://gdal.org/) — the geospatial swiss army knife (X/MIT)
- [shapely](https://shapely.readthedocs.io/) — planar geometry (BSD)
- [pyproj](https://pyproj4.github.io/pyproj/) — CRS transformations (MIT)

Upstream Streamlit version: [AliBgisrs/PlotBounV2](https://github.com/AliBgisrs/PlotBounV2).

---

*Last updated: 2026-05-10 (M1.5 — color customization, multi-format export, origin lock, unit selection, dynamic labels, column-range Plot Group Editor).*
