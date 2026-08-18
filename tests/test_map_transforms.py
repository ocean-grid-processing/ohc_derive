"""map_transforms: area-weighted integral, NaN handling, and the primitive dict."""
import numpy as np

import grid
import map_transforms
import conftest


def _area():
    return grid.cell_area(conftest.LAT, conftest.LON)


def test_integral_of_constant_field():
    fv = conftest.const_field(2.0, n_real=1, n_time=3)
    out = map_transforms.integral(fv)
    assert out.dims == ("realization", "time")
    assert np.allclose(out.values, 2.0 * float(_area().sum()))


def test_integral_drops_nan_cells():
    fv = conftest.const_field(2.0, n_real=1, n_time=2, nan_cells=[(0, 0)])
    kept = float(_area().sum()) - float(_area().isel(lat=0, lon=0))     # the NaN cell leaves the sum
    assert np.allclose(map_transforms.integral(fv).values, 2.0 * kept)


def test_integral_is_linear_across_realizations():
    one = np.full((1, conftest.NLAT, conftest.NLON), 1.0)
    three = np.full((1, conftest.NLAT, conftest.NLON), 3.0)
    fv = conftest.field(np.stack([one, three]), conftest.months(1))    # realizations at 1.0 and 3.0
    out = map_transforms.integral(fv).values
    assert np.allclose(out[1] / out[0], 3.0)


def test_apply_returns_integral_and_map():
    masked = {"15_20": {"field_value": conftest.const_field(5.0, n_real=2, n_time=4), "n_fac": 3}}
    out = map_transforms.apply(masked, level=None)
    assert set(out["15_20"]) == {"integral", "map"}
    assert out["15_20"]["map"] is masked["15_20"]["field_value"]        # gridded field carried through
    assert out["15_20"]["integral"].dims == ("realization", "time")
