"""masks: the fully_wet_nan rule per cell, realization consistency, and the footprint area.

Bathy laid out so, for the 0_700 constituents (15_20, 15_300, 300_700), the top row exercises every
case: (0,0) all fully wet, (0,1) 300_700 intersecting, (0,2) 300_700 dry + 15_300 intersecting.
"""
import numpy as np
import pytest

import masks
import levels
import grid
import conftest

BATHY = conftest.bathy([[1000.0, 500.0, 100.0],
                        [1000.0, 1000.0, 1000.0]])


def cons(f1520, f15300, f300700):
    return [
        conftest.constituent("15_20", 3, 15, 20, f1520),
        conftest.constituent("15_300", 1, 15, 300, f15300),
        conftest.constituent("300_700", 1, 300, 700, f300700),
    ]


def _default():
    return cons(conftest.const_field(1.0), conftest.const_field(10.0), conftest.const_field(100.0))


def test_all_defined_no_exclusions_and_dry_is_zeroed():
    masked, footprint = masks.fully_wet_nan(None, _default(), BATHY)
    assert bool(footprint.all())                                     # 15_20 wet everywhere -> all in footprint
    m300 = masked["300_700"]["field_value"]
    assert np.allclose(m300.isel(lat=0, lon=2).values, 0.0)          # dry -> 0
    assert np.allclose(m300.isel(lat=0, lon=0).values, 100.0)        # fully wet -> value
    assert np.allclose(m300.isel(lat=0, lon=1).values, 100.0)        # intersecting + defined -> value
    assert np.allclose(masked["15_20"]["field_value"].values, 1.0)   # fully wet everywhere


def test_fully_wet_gap_excludes_the_whole_cell():
    f1520 = conftest.const_field(1.0, nan_cells=[(1, 1)])            # 15_20 fully wet at (1,1) but NaN
    masked, footprint = masks.fully_wet_nan(None, cons(
        f1520, conftest.const_field(10.0), conftest.const_field(100.0)), BATHY)
    assert not bool(footprint.isel(lat=1, lon=1))                    # dropped column leaves the footprint
    assert int(footprint.sum()) == 5
    for tag in ("15_20", "15_300", "300_700"):
        assert bool(masked[tag]["field_value"].isel(lat=1, lon=1).isnull().all())


def test_intersecting_nan_contributes_zero_and_does_not_exclude():
    f300 = conftest.const_field(100.0, nan_cells=[(0, 1)])           # 300_700 intersecting at (0,1)
    masked, footprint = masks.fully_wet_nan(None, cons(
        conftest.const_field(1.0), conftest.const_field(10.0), f300), BATHY)
    assert bool(footprint.all())                                     # not a drop: 15_20/15_300 still hold water
    assert np.allclose(masked["300_700"]["field_value"].isel(lat=0, lon=1).values, 0.0)


def test_member_gap_is_consistent_across_realizations():
    f1520 = conftest.const_field(1.0, n_real=2, member_nan=[(1, 1, 0)])   # NaN in the member at (1,0)
    masked, footprint = masks.fully_wet_nan(None, cons(
        f1520, conftest.const_field(10.0, n_real=2), conftest.const_field(100.0, n_real=2)), BATHY)
    assert not bool(footprint.isel(lat=1, lon=0))                    # a member gap drops the cell
    both = masked["15_20"]["field_value"].isel(lat=1, lon=0)
    assert bool(both.isnull().all())                                # NaN in mean and member alike


def test_nan_bathy_is_treated_as_dry():
    b = conftest.bathy([[1000.0, 500.0, np.nan], [1000.0, 1000.0, 1000.0]])
    masked, footprint = masks.fully_wet_nan(None, _default(), b)
    assert not bool(footprint.isel(lat=0, lon=2))                    # all dry there -> outside the footprint
    for tag in ("15_20", "15_300", "300_700"):
        assert np.allclose(masked[tag]["field_value"].isel(lat=0, lon=2).values, 0.0)   # dry -> 0, not NaN


def test_apply_area_covers_the_wet_footprint(tmp_path):
    _, area = masks.apply("fully_wet_nan", levels.get("0_700"), _default(), BATHY, out_dir=str(tmp_path))
    assert np.isclose(area, float(grid.cell_area(conftest.LAT, conftest.LON).sum()))    # every cell is wet


def test_apply_area_drops_excluded_cells(tmp_path):
    f1520 = conftest.const_field(1.0, nan_cells=[(1, 1)])
    _, area = masks.apply("fully_wet_nan", levels.get("0_700"), cons(
        f1520, conftest.const_field(10.0), conftest.const_field(100.0)), BATHY, out_dir=str(tmp_path))
    a = grid.cell_area(conftest.LAT, conftest.LON)
    assert np.isclose(area, float(a.sum()) - float(a.isel(lat=1, lon=1)))


def test_land_is_outside_the_footprint(tmp_path):
    bathy = conftest.bathy([[1000.0, 1000.0, -10.0], [1000.0, 1000.0, 1000.0]])   # (0,2) above sea level
    masked, footprint = masks.fully_wet_nan(None, _default(), bathy)
    assert not bool(footprint.isel(lat=0, lon=2))                    # land holds no water for the level
    assert np.allclose(masked["15_20"]["field_value"].isel(lat=0, lon=2).values, 0.0)
    _, area = masks.apply("fully_wet_nan", levels.get("0_700"), _default(), bathy, out_dir=str(tmp_path))
    a = grid.cell_area(conftest.LAT, conftest.LON)
    assert np.isclose(area, float(a.sum()) - float(a.isel(lat=0, lon=2)))            # land area not counted


def test_apply_unknown_mask_exits(tmp_path):
    with pytest.raises(SystemExit):
        masks.apply("bogus", levels.get("0_700"), _default(), BATHY, out_dir=str(tmp_path))
