"""Load an ohc_ingest *published product* (.nc) as the input to the derive transforms.

The handoff format is the NetCDF that ohc_ingest's publish step emits — not the internal zarr.
The OHC_ submission carries the posterior-mean field (DATA); ensemble uncertainty needs the
per-member OHCENS_ sibling (from `publish.py --ensemble`), located by swapping the filename
prefix. The mask is already applied as NaN by publish, and cell_area is regenerated from the
grid (it's a pure function), so this component needs nothing from upstream but the .nc.
"""
import os

import numpy as np
import xarray as xr

EARTH_RADIUS_M = 6_371_000.0


def _cell_area(lat, lon):
    """Spherical cell area [lat, lon] in m^2, from the coordinate spacing."""
    lat = np.asarray(lat, dtype="float64")
    lon = np.asarray(lon, dtype="float64")
    dlat = abs(lat[1] - lat[0])
    dlon = abs(lon[1] - lon[0])
    s_hi = np.sin(np.deg2rad(lat + dlat / 2))
    s_lo = np.sin(np.deg2rad(lat - dlat / 2))
    area_lat = EARTH_RADIUS_M ** 2 * np.deg2rad(dlon) * (s_hi - s_lo)   # [lat]
    grid = np.repeat(area_lat[:, None], len(lon), axis=1)
    return xr.DataArray(grid, dims=("lat", "lon"), coords={"lat": lat, "lon": lon})


def _to_tlatlon(da):
    return da.transpose("TIME", "LATITUDE", "LONGITUDE").rename(
        {"TIME": "time", "LATITUDE": "lat", "LONGITUDE": "lon"})


def ensemble_sibling(submission_nc):
    """The OHCENS_ path for an OHC_ submission (publish.py --ensemble output)."""
    base = os.path.basename(submission_nc)
    if not base.startswith("OHC_"):
        raise ValueError("expected an OHC_ submission filename, got %r" % base)
    return os.path.join(os.path.dirname(submission_nc), "OHCENS_" + base[len("OHC_"):])


def load_product(submission_nc, with_ensemble=True):
    """Open a published submission as the `product` Dataset.

    Variables:
      ohc       (time, lat, lon)         posterior-mean OHC (TJ/m^2), NaN outside the mask
      ohc_ens   (member, time, lat, lon) ensemble (only if with_ensemble and the sibling exists)
      cell_area (lat, lon)               m^2 (regenerated from the grid)
      usable    (lat, lon)               bool, finite at every timestep
    """
    ds = xr.open_dataset(submission_nc, decode_times=True)
    mean = _to_tlatlon(ds["DATA"])
    data_vars = {
        "ohc": mean,
        "cell_area": _cell_area(mean["lat"].values, mean["lon"].values),
        "usable": mean.notnull().all("time"),
    }
    if with_ensemble:
        ens_nc = ensemble_sibling(submission_nc)
        if not os.path.exists(ens_nc):
            raise FileNotFoundError(
                "%s not found — run publish.py --ensemble, or use --no-ensemble"
                % os.path.basename(ens_nc))
        eds = xr.open_dataset(ens_nc, decode_times=True)
        data_vars["ohc_ens"] = (eds["DATA"]
                                .transpose("MEMBER", "TIME", "LATITUDE", "LONGITUDE")
                                .rename({"MEMBER": "member", "TIME": "time",
                                         "LATITUDE": "lat", "LONGITUDE": "lon"}))
    return xr.Dataset(data_vars, attrs=dict(ds.attrs))
