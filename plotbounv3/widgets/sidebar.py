from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QScrollArea,
    QFrame,
    QPushButton,
)

from ..grid import GridParams
from ..style import PlotStyle
from .color_button import ColorButton


# Unit-aware fields: keys are the public attribute names; canonical stored value is pixels.
_UNIT_FIELDS = ("plot_w", "plot_h", "gap_ew", "gap_ns", "trial_gap", "col_shift_x", "col_shift_y")


class Sidebar(QWidget):
    params_changed = Signal(GridParams)
    style_changed = Signal(PlotStyle)
    lock_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._building = True
        self._origin_x = 100.0
        self._origin_y = 100.0
        self._origin_locked = False

        # Unit state. Px-per-meter is (None, None) when no projected CRS is available.
        self._unit = "px"  # "px" or "m"
        self._px_per_m_x: Optional[float] = None
        self._px_per_m_y: Optional[float] = None

        # Canonical pixel values for unit-aware fields. UI spinboxes display in current unit.
        self._px_values: dict[str, float] = {
            "plot_w": 60.0,
            "plot_h": 40.0,
            "gap_ew": 20.0,
            "gap_ns": 20.0,
            "trial_gap": 100.0,
            "col_shift_x": 0.0,
            "col_shift_y": 0.0,
        }

        self._style = PlotStyle()

        self._build_ui()
        self._building = False

    # -------- public --------
    def set_origin(self, x: float, y: float) -> None:
        self._origin_x = x
        self._origin_y = y
        self._refresh_origin_label()
        self._emit()

    def set_pixel_size(self, px_per_m_x: Optional[float], px_per_m_y: Optional[float]) -> None:
        """Called by MainWindow after loading a raster. None disables meters mode."""
        self._px_per_m_x = px_per_m_x
        self._px_per_m_y = px_per_m_y
        has_meters = px_per_m_x is not None and px_per_m_y is not None
        self.cb_unit.blockSignals(True)
        # Keep current values, just enable/disable the meters option.
        # Rebuild combo to reflect availability.
        self.cb_unit.clear()
        self.cb_unit.addItem("Pixels", "px")
        if has_meters:
            self.cb_unit.addItem("Meters", "m")
        # Restore selection if possible.
        target = self._unit if (self._unit == "px" or has_meters) else "px"
        idx = self.cb_unit.findData(target)
        if idx < 0:
            idx = 0
        self.cb_unit.setCurrentIndex(idx)
        self._unit = self.cb_unit.itemData(idx)
        self.cb_unit.blockSignals(False)
        self.cb_unit.setEnabled(has_meters)
        self._refresh_unit_spinboxes()

    def current_style(self) -> PlotStyle:
        return PlotStyle(
            polygon_color=self.btn_color_normal.color(),
            polygon_edited_color=self.btn_color_edit.color(),
            label_color=self.btn_color_label.color(),
            polygon_width=self.sb_pen_width.value(),
            label_size_px=self.sb_label_size.value(),
            origin_color=self.btn_color_origin.color(),
        )

    def current_params(self) -> GridParams:
        start_ids = self._collect_trial_start_ids()
        # Pull pixel values from canonical store (kept in sync with spinboxes).
        return GridParams(
            origin_x=self._origin_x,
            origin_y=self._origin_y,
            h_dir="right" if self.cb_h.currentIndex() == 0 else "left",
            v_dir="down" if self.cb_v.currentIndex() == 0 else "up",
            num_trials=self.sb_trials.value(),
            trial_start_ids=start_ids,
            serpentine=(self.cb_order.currentIndex() == 1),
            rows_per_trial=self.sb_rows.value(),
            cols=self.sb_cols.value(),
            plot_w=self._px_values["plot_w"],
            plot_h=self._px_values["plot_h"],
            gap_ew=self._px_values["gap_ew"],
            gap_ns=self._px_values["gap_ns"],
            trial_gap=self._px_values["trial_gap"],
            angle=self.dsb_angle.value(),
            col_edit_enabled=self.gb_col.isChecked(),
            col_edit_start_id=self.sb_estart.value(),
            col_edit_end_id=self.sb_eend.value(),
            col_shift_x=self._px_values["col_shift_x"],
            col_shift_y=self._px_values["col_shift_y"],
            col_angle=self.dsb_cangle.value(),
            col_angle_is_delta=True,
        )

    def is_origin_locked(self) -> bool:
        return self._origin_locked

    # -------- internal UI build --------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        v = QVBoxLayout(content)
        v.setContentsMargins(8, 8, 8, 8)

        title = QLabel("<b>Plot Boundary V3</b><br><small>Developed by Ali Bazrafkan</small>")
        title.setWordWrap(True)
        v.addWidget(title)
        v.addWidget(self._hline())

        # --- 1. Field Setup ---
        gb1 = QGroupBox("1. Field Setup")
        f1 = QFormLayout(gb1)

        origin_row = QHBoxLayout()
        self.lbl_origin = QLabel()
        origin_row.addWidget(self.lbl_origin, 1)
        self.btn_lock = QPushButton("\U0001F513 Unlocked")
        self.btn_lock.setCheckable(True)
        self.btn_lock.setToolTip("Lock origin point — clicks on the map will be ignored when locked.")
        self.btn_lock.toggled.connect(self._on_lock_toggled)
        origin_row.addWidget(self.btn_lock)
        f1.addRow(origin_row)

        self.cb_h = QComboBox()
        self.cb_h.addItems(["To the Right (East)", "To the Left (West)"])
        self.cb_v = QComboBox()
        self.cb_v.addItems(["Downward (South)", "Upward (North)"])
        f1.addRow("Horizontal Growth", self.cb_h)
        f1.addRow("Vertical Growth", self.cb_v)

        self.cb_unit = QComboBox()
        self.cb_unit.addItem("Pixels", "px")
        self.cb_unit.setEnabled(False)
        self.cb_unit.setToolTip(
            "Switch input units. Meters becomes available when the raster has a projected CRS."
        )
        f1.addRow("Input Units", self.cb_unit)
        v.addWidget(gb1)

        # --- 2. Trials & Labels ---
        gb2 = QGroupBox("2. Trials && Labels")
        f2 = QFormLayout(gb2)
        self.sb_trials = QSpinBox(); self.sb_trials.setRange(1, 50); self.sb_trials.setValue(1)
        f2.addRow("Number of Trials", self.sb_trials)
        self.trial_ids_container = QWidget()
        self.trial_ids_layout = QFormLayout(self.trial_ids_container)
        self.trial_ids_layout.setContentsMargins(0, 0, 0, 0)
        f2.addRow(self.trial_ids_container)
        self.cb_order = QComboBox(); self.cb_order.addItems(["Straight", "Serpentine"])
        f2.addRow("Labeling Order", self.cb_order)
        v.addWidget(gb2)
        self._rebuild_trial_ids(1)

        # --- 3. Geometry ---
        gb3 = QGroupBox("3. Geometry")
        f3 = QFormLayout(gb3)
        self.sb_rows = QSpinBox(); self.sb_rows.setRange(1, 200); self.sb_rows.setValue(5)
        self.sb_cols = QSpinBox(); self.sb_cols.setRange(1, 200); self.sb_cols.setValue(5)
        self.dsb_pw = self._make_unit_spin("plot_w"); f3.addRow(f"Plot Width ({self._unit_label()})", self.dsb_pw)
        self.dsb_ph = self._make_unit_spin("plot_h"); f3.addRow(f"Plot Height ({self._unit_label()})", self.dsb_ph)
        self.dsb_de = self._make_unit_spin("gap_ew"); f3.addRow(f"E-W Gap ({self._unit_label()})", self.dsb_de)
        self.dsb_dn = self._make_unit_spin("gap_ns"); f3.addRow(f"N-S Gap ({self._unit_label()})", self.dsb_dn)
        self.dsb_trialgap = self._make_unit_spin("trial_gap"); f3.addRow(f"Trial Gap ({self._unit_label()})", self.dsb_trialgap)
        self.dsb_angle = QDoubleSpinBox(); self.dsb_angle.setRange(-360.0, 360.0); self.dsb_angle.setDecimals(2); self.dsb_angle.setSingleStep(0.1)
        # Wire counts (not unit-aware)
        f3.insertRow(0, "Rows per Trial", self.sb_rows)
        f3.insertRow(1, "Total Columns", self.sb_cols)
        f3.addRow("Grid Rotation (deg)", self.dsb_angle)
        v.addWidget(gb3)

        # --- 4. Plot Group Editor (formerly Column-Strip) ---
        self.gb_col = QGroupBox("Plot Group Editor")
        self.gb_col.setCheckable(True)
        self.gb_col.setChecked(False)
        f4 = QFormLayout(self.gb_col)
        self.sb_estart = QSpinBox(); self.sb_estart.setRange(-10**9, 10**9); self.sb_estart.setValue(100)
        self.sb_eend = QSpinBox(); self.sb_eend.setRange(-10**9, 10**9); self.sb_eend.setValue(105)
        range_hint = QLabel(
            "<small>All plots in columns from <b>Start ID's column</b> through "
            "<b>End ID's column</b> (inclusive) will be edited.</small>"
        )
        range_hint.setWordWrap(True)
        self.sb_estart.setToolTip("Plot ID whose column starts the edit range.")
        self.sb_eend.setToolTip("Plot ID whose column ends the edit range.")
        f4.addRow("Start ID", self.sb_estart)
        f4.addRow("End ID", self.sb_eend)
        f4.addRow(range_hint)
        self.dsb_sx = self._make_unit_spin("col_shift_x", allow_negative=True); f4.addRow(f"Shift X ({self._unit_label()})", self.dsb_sx)
        self.dsb_sy = self._make_unit_spin("col_shift_y", allow_negative=True); f4.addRow(f"Shift Y ({self._unit_label()})", self.dsb_sy)
        self.dsb_cangle = QDoubleSpinBox(); self.dsb_cangle.setRange(-360.0, 360.0); self.dsb_cangle.setDecimals(2); self.dsb_cangle.setSingleStep(0.1)
        self.dsb_cangle.setToolTip("Added to the main Grid Rotation for selected plots.")
        f4.addRow("Strip Rotation Δ (deg)", self.dsb_cangle)
        v.addWidget(self.gb_col)

        # --- 5. Colors & Display ---
        gb5 = QGroupBox("5. Colors && Display")
        f5 = QFormLayout(gb5)
        self.btn_color_normal = ColorButton(self._style.polygon_color)
        self.btn_color_edit = ColorButton(self._style.polygon_edited_color)
        self.btn_color_label = ColorButton(self._style.label_color)
        self.btn_color_origin = ColorButton(self._style.origin_color)
        f5.addRow("Polygon Color", self.btn_color_normal)
        f5.addRow("Edited Polygon Color", self.btn_color_edit)
        f5.addRow("Label Color", self.btn_color_label)
        f5.addRow("Origin Marker Color", self.btn_color_origin)
        self.sb_pen_width = QSpinBox(); self.sb_pen_width.setRange(1, 12); self.sb_pen_width.setValue(self._style.polygon_width)
        f5.addRow("Polygon Width (px)", self.sb_pen_width)
        self.sb_label_size = QSpinBox(); self.sb_label_size.setRange(6, 60); self.sb_label_size.setValue(self._style.label_size_px)
        self.sb_label_size.setToolTip(
            "Label font size in SCREEN pixels — stays readable as you zoom in/out."
        )
        f5.addRow("Label Size (px)", self.sb_label_size)
        v.addWidget(gb5)

        v.addStretch(1)

        self._refresh_origin_label()
        self._refresh_unit_spinboxes()
        self._wire_signals()

    # -------- builders / helpers --------
    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _make_unit_spin(self, key: str, allow_negative: bool = False) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setRange(-1e9 if allow_negative else 0.0, 1e9)
        sb.setDecimals(0)
        sb.setSingleStep(1.0)
        sb.setValue(self._px_values[key])
        sb.setProperty("unit_key", key)
        return sb

    def _unit_label(self) -> str:
        return "m" if self._unit == "m" else "px"

    def _refresh_origin_label(self) -> None:
        lock_mark = "🔒 " if self._origin_locked else ""
        if self._unit == "m" and self._px_per_m_x and self._px_per_m_y:
            x_m = self._origin_x / self._px_per_m_x
            y_m = self._origin_y / self._px_per_m_y
            self.lbl_origin.setText(f"{lock_mark}Origin: ({x_m:.2f}, {y_m:.2f}) m")
        else:
            self.lbl_origin.setText(f"{lock_mark}Origin: ({self._origin_x:.1f}, {self._origin_y:.1f}) px")

    def _refresh_unit_spinboxes(self) -> None:
        """Show canonical pixel values converted into the currently-selected unit."""
        pair_keys = (
            ("plot_w", "dsb_pw", "x"),
            ("plot_h", "dsb_ph", "y"),
            ("gap_ew", "dsb_de", "x"),
            ("gap_ns", "dsb_dn", "y"),
            ("trial_gap", "dsb_trialgap", "y"),
            ("col_shift_x", "dsb_sx", "x"),
            ("col_shift_y", "dsb_sy", "y"),
        )
        is_m = (self._unit == "m" and self._px_per_m_x is not None and self._px_per_m_y is not None)
        for key, attr, axis in pair_keys:
            sb: QDoubleSpinBox = getattr(self, attr)
            sb.blockSignals(True)
            if is_m:
                px_per_m = self._px_per_m_x if axis == "x" else self._px_per_m_y
                sb.setDecimals(3)
                sb.setSingleStep(0.01)
                sb.setValue(self._px_values[key] / px_per_m)
            else:
                sb.setDecimals(0)
                sb.setSingleStep(1.0)
                sb.setValue(self._px_values[key])
            sb.blockSignals(False)
        # Relabel form rows by walking each form's labels.
        self._relabel_form_units()
        self._refresh_origin_label()

    def _relabel_form_units(self) -> None:
        u = self._unit_label()
        labels = {
            "dsb_pw": f"Plot Width ({u})",
            "dsb_ph": f"Plot Height ({u})",
            "dsb_de": f"E-W Gap ({u})",
            "dsb_dn": f"N-S Gap ({u})",
            "dsb_trialgap": f"Trial Gap ({u})",
            "dsb_sx": f"Shift X ({u})",
            "dsb_sy": f"Shift Y ({u})",
        }
        for attr, text in labels.items():
            sb = getattr(self, attr, None)
            if sb is None:
                continue
            parent_form = sb.parentWidget().layout() if sb.parentWidget() else None
            if isinstance(parent_form, QFormLayout):
                lbl = parent_form.labelForField(sb)
                if isinstance(lbl, QLabel):
                    lbl.setText(text)

    def _wire_signals(self) -> None:
        # Generator-affecting widgets
        widgets = [
            self.cb_h, self.cb_v, self.cb_order,
            self.sb_rows, self.sb_cols,
            self.dsb_pw, self.dsb_ph, self.dsb_de, self.dsb_dn, self.dsb_trialgap, self.dsb_angle,
            self.sb_estart, self.sb_eend, self.dsb_sx, self.dsb_sy, self.dsb_cangle,
        ]
        for w in widgets:
            if isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self._on_unit_aware_changed)
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                w.valueChanged.connect(self._on_unit_aware_changed)
            elif isinstance(w, QCheckBox):
                w.toggled.connect(self._on_unit_aware_changed)
        self.sb_trials.valueChanged.connect(self._on_trials_changed)
        self.gb_col.toggled.connect(lambda _=None: self._emit())
        self.cb_unit.currentIndexChanged.connect(self._on_unit_changed)

        # Style widgets
        for btn in (self.btn_color_normal, self.btn_color_edit, self.btn_color_label, self.btn_color_origin):
            btn.color_changed.connect(self._emit_style)
        self.sb_pen_width.valueChanged.connect(lambda _=None: self._emit_style())
        self.sb_label_size.valueChanged.connect(lambda _=None: self._emit_style())

    def _on_unit_aware_changed(self, *_):
        # Sync canonical pixel values from the unit-aware spinboxes before emitting params.
        is_m = (self._unit == "m" and self._px_per_m_x is not None and self._px_per_m_y is not None)
        axis_map = {
            "plot_w": ("dsb_pw", "x"),
            "plot_h": ("dsb_ph", "y"),
            "gap_ew": ("dsb_de", "x"),
            "gap_ns": ("dsb_dn", "y"),
            "trial_gap": ("dsb_trialgap", "y"),
            "col_shift_x": ("dsb_sx", "x"),
            "col_shift_y": ("dsb_sy", "y"),
        }
        for key, (attr, axis) in axis_map.items():
            sb: QDoubleSpinBox = getattr(self, attr)
            if is_m:
                px_per_m = self._px_per_m_x if axis == "x" else self._px_per_m_y
                self._px_values[key] = sb.value() * px_per_m
            else:
                self._px_values[key] = sb.value()
        self._emit()

    def _on_unit_changed(self, _idx: int):
        data = self.cb_unit.currentData()
        if data == self._unit:
            return
        self._unit = data
        self._refresh_unit_spinboxes()
        self._emit()

    def _on_lock_toggled(self, checked: bool):
        self._origin_locked = checked
        self.btn_lock.setText("\U0001F512 Locked" if checked else "\U0001F513 Unlocked")
        self._refresh_origin_label()
        self.lock_changed.emit(checked)

    def _on_trials_changed(self, n: int) -> None:
        self._rebuild_trial_ids(n)
        self._emit()

    def _rebuild_trial_ids(self, n: int) -> None:
        existing = []
        for i in range(self.trial_ids_layout.rowCount()):
            item = self.trial_ids_layout.itemAt(i, QFormLayout.FieldRole)
            if item and isinstance(item.widget(), QSpinBox):
                existing.append(item.widget().value())
        while self.trial_ids_layout.rowCount() > 0:
            self.trial_ids_layout.removeRow(0)
        for i in range(n):
            sb = QSpinBox()
            sb.setRange(-10**9, 10**9)
            sb.setValue(existing[i] if i < len(existing) else 100 + i * 100)
            sb.valueChanged.connect(self._emit)
            self.trial_ids_layout.addRow(f"Trial {i+1} Start ID", sb)

    def _collect_trial_start_ids(self) -> list[int]:
        ids = []
        for i in range(self.trial_ids_layout.rowCount()):
            item = self.trial_ids_layout.itemAt(i, QFormLayout.FieldRole)
            if item and isinstance(item.widget(), QSpinBox):
                ids.append(item.widget().value())
        return ids

    def _emit(self) -> None:
        if self._building:
            return
        self.params_changed.emit(self.current_params())

    def _emit_style(self) -> None:
        if self._building:
            return
        self._style = self.current_style()
        self.style_changed.emit(self._style)
