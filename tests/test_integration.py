"""End-to-end run_level scenarios with hand-computed answers: a window, the dry/excluded cells
through the full pipeline, and the multi-constituent deep levels.

Where the answers come from, one step at a time. Each constituent's field is flat in space and rises
linearly in time: value(t) = slope * t, where t is the month index (0, 1, 2, ...).

  Step 3, the integral. This is a spatial integral only: at each timestep it sums over the map cells
  and leaves the time axis alone, so it turns a map-per-month into a number-per-month. Summing a
  spatially flat field over the footprint just multiplies it by the footprint area A, so the time
  series is integral(t) = slope * t * A -- one value per month, still varying with t.

  Step 4, OHCA = anomaly, then annual mean. The anomaly subtracts the record mean of t. Over 24
  months t runs 0..23, whose mean is 11.5, giving anomaly(t) = slope * (t - 11.5) * A. The annual
  mean then averages each calendar year's 12 months:
      year 1 (t = 0..11):  mean t = 5.5  ->  5.5 - 11.5 = -6  ->  -6 * slope * A
      year 2 (t = 12..23): mean t = 17.5 -> 17.5 - 11.5 = +6  ->  +6 * slope * A
  So a slope-1 constituent has OHCA = [-6A, +6A].

  Step 6, the combine. The synthetic level is sum(n_fac_i * OHCA_i). When every constituent shares
  the same field, they share OHCA too, so the result is just sum(n_fac) * [-6A, +6A].

The windowed and dry/excluded cases re-run this arithmetic with their own numbers, spelled out inline.
"""
import types

import numpy as np

import run
import levels
import grid
import conftest

DEEP = conftest.bathy(np.full((conftest.NLAT, conftest.NLON), 3000.0))    # floor below every layer


def ramp(slope=1.0, n_time=24, nan_cells=()):
    t = slope * np.arange(float(n_time))
    arr = t[None, :, None, None] * np.ones((1, n_time, conftest.NLAT, conftest.NLON))
    for (i, j) in nan_cells:
        arr[:, :, i, j] = np.nan
    return conftest.field(arr, conftest.months(n_time, start_year=2001))


def attrs():
    return {"cp0": 3989.0, "rho0": 1030.0}


def cfg(quantities, window, out):
    return types.SimpleNamespace(mask="fully_wet_nan", quantities=quantities, time_window=window, out=out)


def A():
    return float(grid.cell_area(conftest.LAT, conftest.LON).sum())


def test_windowed_ohca_and_trend(tmp_path):
    # 15_20 = t over 36 months (2001-2003); 15_300 = 0. Window 2002-2003 -> baseline = mean(t=12..35) = 23.5.
    # anomaly annualises to [-18A, -6A, 6A]; combine x3 -> [-54A, -18A, 18A].
    # trend over 2002-2003 of the annual integral [17.5A, 29.5A] = 12A/yr; combine x3 -> 36A.
    subs = {
        "15_20": {"field_value": ramp(1.0, 36), "attrs": attrs()},
        "15_300": {"field_value": conftest.const_field(0.0, n_time=36), "attrs": attrs()},
    }
    blob = run.run_level(levels.get("0_300"), subs, DEEP,
                         cfg(["ohca", "ohca_trend"], (2002, 2003), str(tmp_path)))
    a = A()
    assert np.allclose(blob["ohca"].values, [-54 * a, -18 * a, 18 * a])
    assert np.isclose(float(blob["ohca_trend"]), 36 * a)


def test_dry_and_excluded_cells_through_the_full_pipeline(tmp_path):
    # 0_700, all three constituents = t; bathy makes 300_700 dry at (0,1); 15_20 has a gap at (1,0).
    subs = {
        "15_20": {"field_value": ramp(1.0, 12, nan_cells=[(1, 0)]), "attrs": attrs()},
        "15_300": {"field_value": ramp(1.0, 12), "attrs": attrs()},
        "300_700": {"field_value": ramp(1.0, 12), "attrs": attrs()},
    }
    bathy = conftest.bathy([[3000.0, 100.0, 3000.0], [3000.0, 3000.0, 3000.0]])
    blob = run.run_level(levels.get("0_700"), subs, bathy, cfg(["map"], None, str(tmp_path)))
    anom = np.arange(12.0) - 5.5
    assert np.allclose(blob["map"].isel(lat=0, lon=0).values, 5 * anom)    # 3 + 1 + 1 all contribute
    assert np.allclose(blob["map"].isel(lat=0, lon=1).values, 4 * anom)    # 300_700 dry -> dropped
    assert bool(blob["map"].isel(lat=1, lon=0).isnull().all())             # 15_20 gap -> excluded


def test_0_2000_five_constituent_combine(tmp_path):
    lv = levels.get("0_2000")                                              # sum(n_fac) = 9
    subs = {c.tag: {"field_value": ramp(1.0, 24), "attrs": attrs()} for c in lv.contributors}
    blob = run.run_level(lv, subs, DEEP, cfg(["ohca"], None, str(tmp_path)))
    a = A()
    assert np.allclose(blob["ohca"].values, [-54 * a, 54 * a])
    assert np.isclose(blob.attrs["volume_m3"], a * 2000)


def test_700_2000_combine(tmp_path):
    lv = levels.get("700_2000")                                            # sum(n_fac) = 4
    subs = {c.tag: {"field_value": ramp(1.0, 24), "attrs": attrs()} for c in lv.contributors}
    blob = run.run_level(lv, subs, DEEP, cfg(["ohca"], None, str(tmp_path)))
    a = A()
    assert np.allclose(blob["ohca"].values, [-24 * a, 24 * a])
    assert np.isclose(blob.attrs["volume_m3"], a * 1300)
