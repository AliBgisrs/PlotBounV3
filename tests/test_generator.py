"""Generator tests.

- Legacy parity tests verify the core grid math (rotation, growth direction,
  serpentine) still matches PlotBounV2/app.py exactly. These do NOT enable the
  Plot Group Editor, so they are unaffected by the column-range semantics change.
- Column-range tests verify the new Plot Group Editor selects columns from
  Start ID's column through End ID's column, inclusive.
"""
from __future__ import annotations

import math

from plotbounv3.grid import GridParams, generate_plots, rotate_point


# ------------------------------------------------------------------
# Reference grid logic (no column-strip edit) lifted from PlotBounV2/app.py
# ------------------------------------------------------------------
def _ref_rotate_point(x, y, cx, cy, angle_deg):
    angle_rad = math.radians(angle_deg)
    nx = cx + (x - cx) * math.cos(angle_rad) - (y - cy) * math.sin(angle_rad)
    ny = cy + (x - cx) * math.sin(angle_rad) + (y - cy) * math.cos(angle_rad)
    return [nx, ny]


def _ref_generate_no_strip(
    sx, sy, h_dir, v_dir, num_trials, trial_start_ids, order,
    rows_per_trial, cols, pw, ph, de, dn, trial_gap, angle,
):
    mx = 1 if "Right" in h_dir else -1
    my = 1 if "Down" in v_dir else -1
    out = []
    total_y_offset = 0
    for t_idx in range(num_trials):
        cid = trial_start_ids[t_idx]
        for r in range(rows_per_trial):
            is_rev = (order == "Serpentine" and r % 2 != 0)
            for c in range(cols):
                coord_c = (cols - 1 - c) if is_rev else c
                bx = sx + (coord_c * (pw + de) * mx)
                by = sy + (total_y_offset + (r * (ph + dn))) * my
                if mx == -1: bx -= pw
                if my == -1: by -= ph
                corners_px = [
                    _ref_rotate_point(bx, by, sx, sy, angle),
                    _ref_rotate_point(bx + pw, by, sx, sy, angle),
                    _ref_rotate_point(bx + pw, by + ph, sx, sy, angle),
                    _ref_rotate_point(bx, by + ph, sx, sy, angle),
                ]
                out.append((cid, t_idx + 1, corners_px))
                cid += 1
        total_y_offset += (rows_per_trial * (ph + dn)) + trial_gap
    return out


def _params(**overrides) -> GridParams:
    p = GridParams(
        origin_x=200.0, origin_y=300.0,
        h_dir="right", v_dir="down",
        num_trials=2, trial_start_ids=[100, 200],
        serpentine=False,
        rows_per_trial=3, cols=4,
        plot_w=50, plot_h=30, gap_ew=10, gap_ns=8,
        trial_gap=40, angle=0.0,
        col_edit_enabled=False,
        col_edit_start_id=0, col_edit_end_id=0,
        col_shift_x=0, col_shift_y=0, col_angle=0.0,
        col_angle_is_delta=True,
    )
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def _compare_to_reference(params: GridParams):
    ref = _ref_generate_no_strip(
        params.origin_x, params.origin_y,
        "To the Right (East)" if params.h_dir == "right" else "To the Left (West)",
        "Downward (South)" if params.v_dir == "down" else "Upward (North)",
        params.num_trials, params.trial_start_ids,
        "Serpentine" if params.serpentine else "Straight",
        params.rows_per_trial, params.cols, params.plot_w, params.plot_h,
        params.gap_ew, params.gap_ns, params.trial_gap, params.angle,
    )
    new = generate_plots(params)
    assert len(ref) == len(new)
    for (rid, rt, rcorners), plot in zip(ref, new):
        assert plot.id == rid
        assert plot.trial == rt
        for (rx, ry), (nx, ny) in zip(rcorners, plot.corners_px):
            assert math.isclose(rx, nx, abs_tol=1e-9)
            assert math.isclose(ry, ny, abs_tol=1e-9)


# ------------------------------------------------------------------
# Core grid math — parity with original app.py
# ------------------------------------------------------------------
def test_basic_straight():
    _compare_to_reference(_params())


def test_serpentine():
    _compare_to_reference(_params(serpentine=True))


def test_rotated():
    _compare_to_reference(_params(angle=27.5))


def test_growth_left_up():
    _compare_to_reference(_params(h_dir="left", v_dir="up"))


def test_many_trials():
    _compare_to_reference(_params(
        num_trials=4,
        trial_start_ids=[100, 200, 300, 400],
        rows_per_trial=2, cols=3, trial_gap=55,
    ))


# ------------------------------------------------------------------
# Plot Group Editor — column-range semantics
# ------------------------------------------------------------------
def test_column_range_simple():
    """5x5 straight grid, Start=102 (col 2), End=108 (row 1 col 3) → cols 2,3."""
    p = _params(
        num_trials=1, trial_start_ids=[100],
        rows_per_trial=5, cols=5,
        col_edit_enabled=True,
        col_edit_start_id=102,
        col_edit_end_id=108,
        col_shift_x=10,
    )
    plots = generate_plots(p)
    edited_ids = sorted(pl.id for pl in plots if pl.is_edited)
    # cols 2,3 in 5x5 with IDs 100..124: rows 0..4 in those cols.
    # row r col c → id = 100 + r*5 + c
    expected = sorted(100 + r * 5 + c for r in range(5) for c in (2, 3))
    assert edited_ids == expected, f"got {edited_ids}, want {expected}"


def test_column_range_single_column():
    """Start == End → single column edited."""
    p = _params(
        num_trials=1, trial_start_ids=[100],
        rows_per_trial=5, cols=5,
        col_edit_enabled=True,
        col_edit_start_id=107,  # row 1, col 2
        col_edit_end_id=107,
    )
    plots = generate_plots(p)
    edited_ids = sorted(pl.id for pl in plots if pl.is_edited)
    expected = [100 + r * 5 + 2 for r in range(5)]  # col 2 only
    assert edited_ids == expected


def test_column_range_reversed_start_end():
    """User types End < Start by mistake — should still pick the same column range."""
    p = _params(
        num_trials=1, trial_start_ids=[100],
        rows_per_trial=5, cols=5,
        col_edit_enabled=True,
        col_edit_start_id=108,  # col 3
        col_edit_end_id=102,    # col 2
    )
    plots = generate_plots(p)
    edited_ids = sorted(pl.id for pl in plots if pl.is_edited)
    expected = sorted(100 + r * 5 + c for r in range(5) for c in (2, 3))
    assert edited_ids == expected


def test_column_range_does_not_bleed_to_unrelated_columns():
    """5x5 grid, Start=100 End=101: only cols 0,1 — definitely NOT all 25 plots."""
    p = _params(
        num_trials=1, trial_start_ids=[100],
        rows_per_trial=5, cols=5,
        col_edit_enabled=True,
        col_edit_start_id=100,  # col 0
        col_edit_end_id=101,    # col 1
    )
    plots = generate_plots(p)
    edited_count = sum(1 for pl in plots if pl.is_edited)
    assert edited_count == 10, f"expected 10 (5 rows * 2 cols), got {edited_count}"
    edited_cols = {pl.id % 5 for pl in plots if pl.is_edited}
    assert edited_cols == {0, 1}


def test_column_range_serpentine_uses_physical_column():
    """With serpentine, ID 105 lives at physical col 4 (row 1, reversed).
    Start=100 (col 0) End=105 (col 4) → all columns edited."""
    p = _params(
        num_trials=1, trial_start_ids=[100],
        rows_per_trial=2, cols=5,
        serpentine=True,
        col_edit_enabled=True,
        col_edit_start_id=100,  # row 0, col 0
        col_edit_end_id=105,    # row 1 (reversed), physical col 4
    )
    plots = generate_plots(p)
    edited_cols = {pl.id % 5 if pl.id < 105 else 9 - (pl.id % 5) for pl in plots if pl.is_edited}
    # Simpler check: all 10 plots edited (every column from 0 to 4)
    assert sum(1 for pl in plots if pl.is_edited) == 10


def test_column_range_angle_delta_applies_to_edited_cols():
    """Grid rotation 30°, strip delta 15° → edited plots get 45°."""
    p = _params(
        num_trials=1, trial_start_ids=[100],
        rows_per_trial=1, cols=3,
        angle=30.0,
        col_edit_enabled=True,
        col_edit_start_id=100,  # col 0
        col_edit_end_id=100,    # col 0 only
        col_angle=15.0,
        col_angle_is_delta=True,
    )
    plots = generate_plots(p)
    edited = next(pl for pl in plots if pl.is_edited)
    pw, ph = p.plot_w, p.plot_h
    sx, sy = p.origin_x, p.origin_y
    bx, by = sx, sy
    expected = [
        rotate_point(bx, by, sx, sy, 45.0),
        rotate_point(bx + pw, by, sx, sy, 45.0),
        rotate_point(bx + pw, by + ph, sx, sy, 45.0),
        rotate_point(bx, by + ph, sx, sy, 45.0),
    ]
    for (ex, ey), (ax, ay) in zip(expected, edited.corners_px):
        assert math.isclose(ex, ax, abs_tol=1e-9)
        assert math.isclose(ey, ay, abs_tol=1e-9)


def test_column_range_disabled_means_no_edits():
    p = _params(col_edit_enabled=False, col_edit_start_id=100, col_edit_end_id=110)
    plots = generate_plots(p)
    assert all(not pl.is_edited for pl in plots)


def test_column_range_invalid_ids_means_no_edits():
    """If Start ID and End ID don't match any plot, nothing is edited (no crash)."""
    p = _params(
        col_edit_enabled=True,
        col_edit_start_id=99999,
        col_edit_end_id=99998,
    )
    plots = generate_plots(p)
    assert all(not pl.is_edited for pl in plots)


if __name__ == "__main__":
    test_basic_straight()
    test_serpentine()
    test_rotated()
    test_growth_left_up()
    test_many_trials()
    test_column_range_simple()
    test_column_range_single_column()
    test_column_range_reversed_start_end()
    test_column_range_does_not_bleed_to_unrelated_columns()
    test_column_range_serpentine_uses_physical_column()
    test_column_range_angle_delta_applies_to_edited_cols()
    test_column_range_disabled_means_no_edits()
    test_column_range_invalid_ids_means_no_edits()
    print("All grid generator tests passed.")
