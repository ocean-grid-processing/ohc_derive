"""Transforms vs. analytic expectations on small synthetic fields."""
import numpy as np

import transforms


def test_timemean_constant(build_product):
    p = build_product(np.full((6, 2, 3), 5.0))
    out = transforms.time_mean(p["ohc"], p)
    assert np.allclose(out["ohc_timemean"].values, 5)


def test_trend_linear_recovers_slope(build_product):
    nt = 24
    p0 = build_product(np.zeros((nt, 2, 3)))
    t = p0["ohc"]["time"].values
    tsec = transforms._time_seconds(p0["ohc"]).values   # uniform-month axis the trend uses
    slope = 3.0e-9                                       # TJ/m^2 per second
    ohc = (slope * tsec)[:, None, None] * np.ones((nt, 2, 3))
    p = build_product(ohc, times=t)
    out = transforms.trend(p["ohc"], p)
    assert np.allclose(out["ohc_trend"].values, slope, rtol=1e-5)  # float32 field storage


def test_trend_constant_is_zero(build_product):
    p = build_product(np.full((12, 2, 2), 7.0))
    out = transforms.trend(p["ohc"], p)
    assert np.allclose(out["ohc_trend"].values, 0.0, atol=1e-12)


def test_trend_masks_unusable(build_product):
    ohc = np.random.RandomState(0).rand(12, 2, 2)
    usable = np.ones((2, 2), bool)
    usable[0, 0] = False
    p = build_product(ohc, usable=usable)
    out = transforms.trend(p["ohc"], p)
    assert np.isnan(out["ohc_trend"].values[0, 0])
    assert np.isfinite(out["ohc_trend"].values[1, 1])


def test_integral_constant(build_product):
    p = build_product(np.full((4, 2, 3), 2.0))
    out = transforms.integral(p["ohc"], p)
    expected = 2.0 * float(p["cell_area"].sum())
    assert np.allclose(out["ohc_integral"].values, expected)


def test_integral_excludes_nan_cells(build_product):
    ohc = np.full((4, 2, 2), 2.0)
    ohc[:, 0, 0] = np.nan                            # a masked cell (NaN in the field)
    p = build_product(ohc)
    out = transforms.integral(p["ohc"], p)
    ca = p["cell_area"].values
    expected = 2.0 * (ca.sum() - ca[0, 0])
    assert np.allclose(out["ohc_integral"].values, expected)


def test_integral_anom_removes_time_mean(build_product):
    # OHCA = integral minus its all-time mean: zero-mean by construction, == demeaned integral
    nt = 6
    ramp = np.arange(nt, dtype="float64")                # 0..5, uniform in space
    field = ramp[:, None, None] * np.ones((nt, 2, 3))
    p = build_product(field)
    integ = transforms.integral(p["ohc"], p)["ohc_integral"]
    out = transforms.integral_anom(p["ohc"], p)["ohc_integral_anom"]
    scale = float(np.abs(integ).max())                   # integral ~ ramp x cell_area, ~1e9+ TJ
    assert np.allclose(out.mean("time").values, 0.0, atol=1e-12 * scale)  # zero-mean to f64 roundoff
    assert np.allclose(out.values, (integ - integ.mean("time")).values)


def test_integral_tendency_is_backward_difference(build_product):
    # OHU = backward difference on the full time axis, NaN at t0
    nt = 5
    ramp = np.arange(nt, dtype="float64") ** 2           # 0,1,4,9,16 -> diffs vary
    field = ramp[:, None, None] * np.ones((nt, 2, 2))
    p = build_product(field)
    integ = transforms.integral(p["ohc"], p)["ohc_integral"].values
    out = transforms.integral_tendency(p["ohc"], p)["ohc_integral_tendency"]
    assert out.sizes["time"] == nt                       # same axis as the other series
    vals = out.values
    assert np.isnan(vals[0])                             # no prior month at t0
    assert np.allclose(vals[1:], np.diff(integ))         # integral(t) - integral(t-1) elsewhere


def test_anomaly_seasonal_only(build_product):
    # 2 years, pure seasonal cycle, no trend -> anom == 0, anom12 == season - mean(season)
    nt = 24
    season = np.array([(m % 12) - 5.5 for m in range(12)], dtype="float64")
    field = np.zeros((nt, 2, 2))
    for t in range(nt):
        field[t, :, :] = 10.0 + season[t % 12]
    p = build_product(field)
    out = transforms.anomaly(p["ohc"], p)
    assert np.allclose(out["ohc_anom"].values, 0.0, atol=1e-12)
    a12 = out["ohc_anom12"].values                  # (month, lat, lon), month 1..12
    assert np.allclose(a12[:, 0, 0], season - season.mean(), atol=1e-12)


def test_anomaly_is_centered(build_product):
    p = build_product(np.random.RandomState(1).rand(24, 2, 2))
    out = transforms.anomaly(p["ohc"], p)
    assert np.allclose(out["ohc_anom"].mean("time").values, 0.0, atol=1e-5)
    assert np.allclose(out["ohc_anom12"].mean("month").values, 0.0, atol=1e-5)


def test_area_excludes_unusable(build_product):
    usable = np.array([[True, False], [True, True]])
    p = build_product(np.ones((2, 2, 2)), usable=usable)
    out = transforms.area(p["ohc"], p)
    ca = p["cell_area"].values
    assert np.allclose(float(out["area_total"]), ca.sum() - ca[0, 1])
