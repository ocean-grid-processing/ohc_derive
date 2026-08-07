"""Shared fixtures. Puts the ohc_derive module dir on sys.path so the flat modules
(`loader`, `transforms`, `ensemble`, `derive`) import the same way they do at runtime.
"""
import os
import sys

# ohc_derive/ is the parent of tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np            # noqa: E402
import pandas as pd          # noqa: E402  (ships with xarray)
import pytest                # noqa: E402
import xarray as xr          # noqa: E402

import loader                # noqa: E402


def _months(n, start="2004-01-15"):
    """n monthly day-15 timestamps as datetime64[ns]."""
    return pd.date_range(start, periods=n, freq=pd.DateOffset(months=1)).values


def _default_attrs():
    return {
        "cp0": 3989.244, "rho0": 1030.0,
        "product": "TEST", "experiment": "B", "period": "2004_2004",
        "layer_m": "0_300", "mapped_layer": "0_300",
        "var_name": "potentialTemperature", "model_name": "SpaceTimeTrend",
        "mask_preset": "me4oh", "source": "test",
    }


@pytest.fixture
def months():
    return _months


@pytest.fixture
def build_product():
    """Factory: in-memory `product` Dataset (ohc[, ohc_ens], cell_area, usable)."""
    def _b(ohc, ohc_ens=None, usable=None, times=None, attrs=None):
        nt, nla, nlo = ohc.shape
        if times is None:
            times = _months(nt)
        lat = -89.5 + np.arange(nla)
        lon = 20.5 + np.arange(nlo)
        coords = {"time": times, "lat": lat, "lon": lon}
        dv = {"ohc": xr.DataArray(ohc.astype("float32"), dims=("time", "lat", "lon"), coords=coords)}
        if ohc_ens is not None:
            mem = np.arange(1, ohc_ens.shape[0] + 1)
            dv["ohc_ens"] = xr.DataArray(
                ohc_ens.astype("float32"), dims=("member", "time", "lat", "lon"),
                coords={"member": mem, "time": times, "lat": lat, "lon": lon})
        dv["cell_area"] = loader._cell_area(lat, lon)
        if usable is None:
            usable = np.ones((nla, nlo), bool)
        dv["usable"] = xr.DataArray(np.asarray(usable), dims=("lat", "lon"),
                                    coords={"lat": lat, "lon": lon})
        return xr.Dataset(dv, attrs=attrs or {})
    return _b


@pytest.fixture
def write_pair(tmp_path):
    """Factory: write an OHC_ submission (+ OHCENS_ sibling) like publish.py does.

    Returns (submission_path, info) where info has the raw mean/ens/coords.
    """
    def _w(nan_cell=None, write_sibling=True, nt=4, nla=2, nlo=3, nmem=3):
        times = _months(nt)
        lat = -89.5 + np.arange(nla)
        lon = 20.5 + np.arange(nlo)
        rng = np.random.RandomState(0)
        mean = rng.rand(nt, nla, nlo).astype("float32")
        ens = rng.rand(nmem, nt, nla, nlo).astype("float32")
        if nan_cell is not None:
            i, j = nan_cell
            mean[:, i, j] = np.nan
            ens[:, :, i, j] = np.nan
        days = ((times - np.datetime64("1900-01-01")) / np.timedelta64(1, "D")).astype("float64")
        attrs = _default_attrs()

        sub = tmp_path / "OHC_2004_2004_lev0_300_expB_TEST.nc"
        ds = xr.Dataset(
            {"DATA": (("LONGITUDE", "LATITUDE", "TIME"), np.transpose(mean, (2, 1, 0)))},
            coords={"LONGITUDE": lon, "LATITUDE": lat, "TIME": days})
        ds["TIME"].attrs = {"units": "days since 1900-01-01 00:00:00", "calendar": "proleptic_gregorian"}
        ds["DATA"].attrs = {"units": "TJ/m^2"}
        ds.attrs = attrs
        ds.to_netcdf(sub)

        if write_sibling:
            eds = xr.Dataset(
                {"DATA": (("MEMBER", "LONGITUDE", "LATITUDE", "TIME"), np.transpose(ens, (0, 3, 2, 1)))},
                coords={"MEMBER": np.arange(1, nmem + 1), "LONGITUDE": lon, "LATITUDE": lat, "TIME": days})
            eds["TIME"].attrs = ds["TIME"].attrs
            eds["DATA"].attrs = {"units": "TJ/m^2"}
            eds.attrs = attrs
            eds.to_netcdf(tmp_path / "OHCENS_2004_2004_lev0_300_expB_TEST.nc")

        return str(sub), {"mean": mean, "ens": ens, "lat": lat, "lon": lon, "times": times}
    return _w
