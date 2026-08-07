"""Loader: .nc round-trip, cell_area regeneration, usable mask, sibling resolution."""
import numpy as np
import pytest

import loader


def test_load_basic(write_pair):
    sub, info = write_pair()
    p = loader.load_product(sub, with_ensemble=True)
    assert p["ohc"].dims == ("time", "lat", "lon")
    assert "ohc_ens" in p
    assert p["ohc_ens"].dims == ("member", "time", "lat", "lon")
    assert p["cell_area"].dims == ("lat", "lon")
    assert bool((p["cell_area"] > 0).all())
    assert np.allclose(p["ohc"].transpose("time", "lat", "lon").values,
                       info["mean"], atol=1e-4, equal_nan=True)


def test_usable_from_nan(write_pair):
    sub, _ = write_pair(nan_cell=(0, 0))
    p = loader.load_product(sub, with_ensemble=False)
    assert not bool(p["usable"].values[0, 0])
    assert bool(p["usable"].values[1, 1])


def test_no_ensemble_skips_sibling(write_pair):
    sub, _ = write_pair(write_sibling=True)
    p = loader.load_product(sub, with_ensemble=False)
    assert "ohc_ens" not in p


def test_missing_sibling_raises(write_pair):
    sub, _ = write_pair(write_sibling=False)
    with pytest.raises(FileNotFoundError):
        loader.load_product(sub, with_ensemble=True)


def test_sibling_name_resolution():
    assert loader.ensemble_sibling("/a/b/OHC_x_y.nc").endswith("/OHCENS_x_y.nc")
    with pytest.raises(ValueError):
        loader.ensemble_sibling("/a/b/not_a_submission.nc")
