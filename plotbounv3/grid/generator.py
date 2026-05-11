"""Parametric plot-grid generator. Core math ported from PlotBounV2/app.py.

Plot Group Editor uses column-RANGE selection: the column containing the Start
ID through the column containing the End ID, inclusive. All plots in those
columns are edited. Order of Start/End is irrelevant — min/max is taken.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


def rotate_point(x: float, y: float, cx: float, cy: float, angle_deg: float) -> list[float]:
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    nx = cx + (x - cx) * cos_a - (y - cy) * sin_a
    ny = cy + (x - cx) * sin_a + (y - cy) * cos_a
    return [nx, ny]


@dataclass
class GridParams:
    origin_x: float = 100.0
    origin_y: float = 100.0

    h_dir: str = "right"  # "right" or "left"
    v_dir: str = "down"   # "down" or "up"

    num_trials: int = 1
    trial_start_ids: list[int] = field(default_factory=lambda: [100])
    serpentine: bool = False

    rows_per_trial: int = 5
    cols: int = 5
    plot_w: float = 60.0
    plot_h: float = 40.0
    gap_ew: float = 20.0
    gap_ns: float = 20.0
    trial_gap: float = 100.0
    angle: float = 0.0

    col_edit_enabled: bool = False
    col_edit_start_id: int = 100
    col_edit_end_id: int = 105
    col_shift_x: float = 0.0
    col_shift_y: float = 0.0
    col_angle: float = 0.0

    # True (default): col_angle is added to the grid rotation for edited plots.
    # False: col_angle replaces the grid rotation for edited plots (legacy app.py).
    col_angle_is_delta: bool = True


@dataclass
class Plot:
    id: int
    trial: int
    corners_px: list[list[float]]
    corners_geo: list[list[float]]
    center_px: list[float]
    is_edited: bool


def _resolve_target_columns(params: GridParams) -> set[int]:
    """Find the columns of Start ID and End ID, return the inclusive range."""
    if not params.col_edit_enabled:
        return set()
    start_col: Optional[int] = None
    end_col: Optional[int] = None
    for t_idx in range(params.num_trials):
        cid = _start_id(params, t_idx)
        for r in range(params.rows_per_trial):
            is_rev = params.serpentine and r % 2 != 0
            for c in range(params.cols):
                coord_c = (params.cols - 1 - c) if is_rev else c
                if cid == params.col_edit_start_id:
                    start_col = coord_c
                if cid == params.col_edit_end_id:
                    end_col = coord_c
                cid += 1
    if start_col is None and end_col is None:
        return set()
    if start_col is None:
        return {end_col}  # type: ignore[arg-type]
    if end_col is None:
        return {start_col}
    lo, hi = (start_col, end_col) if start_col <= end_col else (end_col, start_col)
    return set(range(lo, hi + 1))


def generate_plots(params: GridParams, transform=None) -> list[Plot]:
    sx = params.origin_x
    sy = params.origin_y
    mx = 1 if params.h_dir == "right" else -1
    my = 1 if params.v_dir == "down" else -1
    pw = params.plot_w
    ph = params.plot_h
    de = params.gap_ew
    dn = params.gap_ns

    target_cols = _resolve_target_columns(params)

    plots: list[Plot] = []
    total_y_offset = 0.0
    for t_idx in range(params.num_trials):
        cid = _start_id(params, t_idx)
        for r in range(params.rows_per_trial):
            is_rev = params.serpentine and r % 2 != 0
            for c in range(params.cols):
                coord_c = (params.cols - 1 - c) if is_rev else c
                is_strip_edited = params.col_edit_enabled and (coord_c in target_cols)

                if is_strip_edited:
                    current_angle = (params.angle + params.col_angle) if params.col_angle_is_delta else params.col_angle
                else:
                    current_angle = params.angle

                bx = sx + (coord_c * (pw + de) * mx) + (params.col_shift_x if is_strip_edited else 0)
                by = sy + (total_y_offset + (r * (ph + dn))) * my + (params.col_shift_y if is_strip_edited else 0)

                if mx == -1:
                    bx -= pw
                if my == -1:
                    by -= ph

                corners_px = [
                    rotate_point(bx, by, sx, sy, current_angle),
                    rotate_point(bx + pw, by, sx, sy, current_angle),
                    rotate_point(bx + pw, by + ph, sx, sy, current_angle),
                    rotate_point(bx, by + ph, sx, sy, current_angle),
                ]
                center = rotate_point(bx + pw / 2, by + ph / 2, sx, sy, current_angle)

                if transform is not None:
                    corners_geo = [list(transform * (p[0], p[1])) for p in corners_px]
                else:
                    corners_geo = [list(p) for p in corners_px]

                plots.append(Plot(
                    id=cid,
                    trial=t_idx + 1,
                    corners_px=corners_px,
                    corners_geo=corners_geo,
                    center_px=center,
                    is_edited=is_strip_edited,
                ))
                cid += 1
        total_y_offset += (params.rows_per_trial * (ph + dn)) + params.trial_gap

    return plots


def _start_id(params: GridParams, trial_idx: int) -> int:
    if trial_idx < len(params.trial_start_ids):
        return params.trial_start_ids[trial_idx]
    return 100 + trial_idx * 100
