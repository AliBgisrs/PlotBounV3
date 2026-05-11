from __future__ import annotations

import os
import traceback
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QDockWidget,
    QProgressDialog,
    QApplication,
    QLabel,
    QMenu,
)

from .canvas import MapView, PlotLayer
from .grid import GridParams, Plot, generate_plots
from .io import export_by_format
from .raster import RasterSource, ensure_overviews
from .style import PlotStyle
from .widgets import Sidebar


RASTER_FILTER = "Rasters (*.tif *.tiff *.jp2 *.png *.jpg *.jpeg);;All files (*.*)"

_EXPORT_FORMATS = [
    ("GeoJSON", "geojson", "GeoJSON (*.geojson *.json)", ".geojson"),
    ("ESRI Shapefile", "shapefile", "Shapefile (*.shp)", ".shp"),
    ("GeoPackage", "geopackage", "GeoPackage (*.gpkg)", ".gpkg"),
    ("File Geodatabase", "gdb", "File Geodatabase (*.gdb)", ".gdb"),
]


class OverviewWorker(QThread):
    finished_ok = Signal(bool)
    failed = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    def run(self) -> None:
        try:
            built = ensure_overviews(self._path)
            self.finished_ok.emit(built)
        except Exception as e:
            self.failed.emit(f"{e}\n{traceback.format_exc()}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plot Boundary V3")
        self.resize(1400, 900)

        self.map_view = MapView()
        self.setCentralWidget(self.map_view)
        self.plot_layer = PlotLayer(self.map_view.scene())

        self.sidebar = Sidebar()
        dock = QDockWidget("Configuration", self)
        dock.setWidget(self.sidebar)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        dock.setMinimumWidth(340)

        self._source: Optional[RasterSource] = None
        self._plots: list[Plot] = []
        self._current_path: Optional[str] = None
        self._overview_worker: Optional[OverviewWorker] = None
        self._overview_progress: Optional[QProgressDialog] = None

        self._build_actions()
        self._build_menus()
        self._build_statusbar()

        self.map_view.origin_clicked.connect(self._on_origin_clicked)
        self.sidebar.params_changed.connect(self._on_params_changed)
        self.sidebar.style_changed.connect(self._on_style_changed)
        self.sidebar.lock_changed.connect(self._on_lock_changed)

        # Apply initial style.
        self.plot_layer.set_style(self.sidebar.current_style())
        self.map_view.set_origin_color(self.sidebar.current_style().origin_color)

    # ---------- actions / menus ----------
    def _build_actions(self) -> None:
        self.act_open = QAction("&Open Orthomosaic...", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self._open_dialog)

        self.act_quit = QAction("&Quit", self)
        self.act_quit.setShortcut(QKeySequence.Quit)
        self.act_quit.triggered.connect(self.close)

        self.act_fit = QAction("&Fit to View", self)
        self.act_fit.setShortcut("Ctrl+0")
        self.act_fit.triggered.connect(self._fit_view)

        # Per-format export actions
        self._export_actions: list[QAction] = []
        for label, fmt, _filter, _ext in _EXPORT_FORMATS:
            act = QAction(f"Export to &{label}...", self)
            act.setEnabled(False)
            act.triggered.connect(lambda checked=False, f=fmt: self._export_format(f))
            self._export_actions.append(act)

    def _build_menus(self) -> None:
        m_file = self.menuBar().addMenu("&File")
        m_file.addAction(self.act_open)
        export_menu = QMenu("&Export", self)
        for act in self._export_actions:
            export_menu.addAction(act)
        m_file.addMenu(export_menu)
        m_file.addSeparator()
        m_file.addAction(self.act_quit)

        m_view = self.menuBar().addMenu("&View")
        m_view.addAction(self.act_fit)

    def _build_statusbar(self) -> None:
        self.lbl_image = QLabel("No image loaded")
        self.lbl_plots = QLabel("Plots: 0")
        self.statusBar().addWidget(self.lbl_image, 1)
        self.statusBar().addPermanentWidget(self.lbl_plots)

    # ---------- open ----------
    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Orthomosaic", "", RASTER_FILTER)
        if not path:
            return
        self._open_path(path)

    def _open_path(self, path: str) -> None:
        self._current_path = path
        try:
            from .raster.overviews import needs_overviews
            if needs_overviews(path):
                ans = QMessageBox.question(
                    self,
                    "Build Overviews?",
                    "This raster has no pyramids. Build them now for fast pan/zoom?\n\n"
                    "This embeds pyramids inside the file (~5-10% size increase, no pixel data lost).",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if ans == QMessageBox.Yes:
                    self._run_overviews(path)
                    return
        except Exception as e:
            QMessageBox.warning(self, "Overview check failed", str(e))

        self._load_source(path)

    def _run_overviews(self, path: str) -> None:
        self._overview_progress = QProgressDialog("Building overviews...", None, 0, 0, self)
        self._overview_progress.setWindowModality(Qt.ApplicationModal)
        self._overview_progress.setMinimumDuration(0)
        self._overview_progress.setCancelButton(None)
        self._overview_progress.show()
        QApplication.processEvents()

        self._overview_worker = OverviewWorker(path)
        self._overview_worker.finished_ok.connect(self._on_overviews_done)
        self._overview_worker.failed.connect(self._on_overviews_failed)
        self._overview_worker.start()

    def _on_overviews_done(self, built: bool) -> None:
        if self._overview_progress is not None:
            self._overview_progress.close()
            self._overview_progress = None
        if self._current_path:
            self._load_source(self._current_path)

    def _on_overviews_failed(self, msg: str) -> None:
        if self._overview_progress is not None:
            self._overview_progress.close()
            self._overview_progress = None
        QMessageBox.warning(
            self,
            "Could not build overviews",
            f"Continuing without overviews (pan/zoom may be slow):\n\n{msg}",
        )
        if self._current_path:
            self._load_source(self._current_path)

    def _load_source(self, path: str) -> None:
        try:
            source = RasterSource(path)
        except Exception as e:
            QMessageBox.critical(self, "Open failed", f"Could not open raster:\n{e}")
            return
        self._source = source
        self.map_view.set_source(source)

        # Inform sidebar whether meter-unit mode is available.
        px_x, px_y = self._compute_pixel_per_meter(source)
        self.sidebar.set_pixel_size(px_x, px_y)

        cx = source.width / 2.0
        cy = source.height / 2.0
        self.map_view.set_origin(cx, cy)
        self.sidebar.set_origin(cx, cy)

        crs = source.crs.to_string() if source.crs else "(no CRS)"
        self.lbl_image.setText(
            f"{os.path.basename(path)} — {source.width}x{source.height}, "
            f"{source.count} bands, {source.dtype}, {crs}"
        )
        for act in self._export_actions:
            act.setEnabled(True)
        self._regenerate()

    @staticmethod
    def _compute_pixel_per_meter(source: RasterSource) -> tuple[Optional[float], Optional[float]]:
        """Returns (px_per_m_x, px_per_m_y) for a projected metric CRS, or (None, None)."""
        if source.crs is None or source.transform is None:
            return (None, None)
        # Only enable meter mode when the CRS is projected with meter linear units.
        try:
            if source.crs.is_geographic:
                return (None, None)
            unit = (source.crs.linear_units or "").lower()
            if unit not in ("metre", "meter", "metres", "meters", "m"):
                return (None, None)
        except Exception:
            return (None, None)
        t = source.transform
        try:
            px_per_m_x = 1.0 / abs(t.a)
            px_per_m_y = 1.0 / abs(t.e)
            return (px_per_m_x, px_per_m_y)
        except Exception:
            return (None, None)

    # ---------- generation ----------
    def _on_origin_clicked(self, x: float, y: float) -> None:
        self.map_view.set_origin(x, y)
        self.sidebar.set_origin(x, y)

    def _on_params_changed(self, params: GridParams) -> None:
        self._regenerate(params)

    def _on_style_changed(self, style: PlotStyle) -> None:
        self.plot_layer.set_style(style)
        self.map_view.set_origin_color(style.origin_color)

    def _on_lock_changed(self, locked: bool) -> None:
        self.map_view.set_origin_locked(locked)

    def _regenerate(self, params: Optional[GridParams] = None) -> None:
        if self._source is None:
            return
        if params is None:
            params = self.sidebar.current_params()
        try:
            self._plots = generate_plots(params, transform=self._source.transform)
        except Exception as e:
            QMessageBox.critical(self, "Grid generation failed", str(e))
            return
        self.plot_layer.render(self._plots)
        self.lbl_plots.setText(f"Plots: {len(self._plots)}")

    # ---------- export ----------
    def _export_format(self, fmt: str) -> None:
        if not self._plots:
            QMessageBox.information(self, "Nothing to export", "Generate a grid first.")
            return
        match = next((row for row in _EXPORT_FORMATS if row[1] == fmt), None)
        if match is None:
            return
        label, _fmt, file_filter, default_ext = match
        default_name = f"plots{default_ext}"
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export to {label}", default_name, file_filter
        )
        if not path:
            return
        if not path.lower().endswith(default_ext.lower()):
            path += default_ext
        crs = self._source.crs.to_string() if (self._source and self._source.crs) else None
        try:
            export_by_format(self._plots, path, fmt=fmt, crs=crs)
        except Exception as e:
            QMessageBox.critical(self, f"Export to {label} failed", str(e))
            return
        self.statusBar().showMessage(f"Exported {len(self._plots)} plots to {path}", 5000)

    # ---------- view ----------
    def _fit_view(self) -> None:
        if self._source is None:
            return
        self.map_view.resetTransform()
        self.map_view.fitInView(self.map_view.scene().sceneRect(), Qt.KeepAspectRatio)
        self.map_view._schedule_redraw()
