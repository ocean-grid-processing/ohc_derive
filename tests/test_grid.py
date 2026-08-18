"""grid.cell_area: shape, positivity, geometry, and the total-sphere sanity check."""
import numpy as np

import grid
import conftest


def test_shape_and_coords():
    a = grid.cell_area(conftest.LAT, conftest.LON)
    assert a.dims == ("lat", "lon")
    assert a.shape == (conftest.NLAT, conftest.NLON)


def test_all_positive():
    a = grid.cell_area(conftest.LAT, conftest.LON)
    assert bool((a > 0).all())


def test_symmetric_grid_is_equal_area():
    # -45 and +45 are symmetric, so both rows have identical cell area
    a = grid.cell_area(conftest.LAT, conftest.LON).values
    assert np.allclose(a, a[0, 0])


def test_equator_cells_larger_than_polar():
    lat = np.array([1.5, 88.5])                     # near-equator vs near-pole, 1-degree cells
    lon = np.array([0.5, 1.5])
    a = grid.cell_area(lat, lon).values
    assert a[0, 0] > a[1, 0]


def test_global_grid_sums_to_sphere():
    lat = np.arange(-89.5, 90, 1.0)
    lon = np.arange(0.5, 360, 1.0)
    total = float(grid.cell_area(lat, lon).sum())
    sphere = 4 * np.pi * grid.EARTH_RADIUS_M ** 2
    assert abs(total - sphere) / sphere < 1e-6
