"""Step 1 (load) and the final write.

`load_submissions` reads each native-level submission (mean field) and, unless mean-only, its member
sibling, and stacks them as `field_value` on a leading `realization` axis (index 0 = mean field, the
rest = members), so downstream steps treat every realization the same way.

`load_bathy` reads the standard bathymetry as a depth grid.

`write_blob` writes one synthetic level's dataset (each quantity plus its `_sd`) with the provenance
tag and link.
"""
import os

import numpy as np
import xarray as xr


def _to_tlatlon(da):
    return da.transpose("TIME", "LATITUDE", "LONGITUDE").rename(
        {"TIME": "time", "LATITUDE": "lat", "LONGITUDE": "lon"})


def _member_sibling(path):
    base = os.path.basename(path)
    if not base.startswith("OHC_"):
        return None
    return os.path.join(os.path.dirname(path), "OHCENS_" + base[len("OHC_"):])


def _load_members(path):
    sib = _member_sibling(path)
    if sib is None or not os.path.exists(sib):
        raise SystemExit("no member sibling for %s (looked for %s); pass --no-ensemble for mean only"
                         % (os.path.basename(path), os.path.basename(sib) if sib else "OHCENS_..."))
    da = xr.open_dataset(sib, decode_times=True)["DATA"]
    return (da.transpose("MEMBER", "TIME", "LATITUDE", "LONGITUDE")
              .rename({"MEMBER": "realization", "TIME": "time", "LATITUDE": "lat", "LONGITUDE": "lon"})
              .astype("float64"))


def _stack(mean_da, member_da):
    """(time, lat, lon) mean + optional (realization, time, lat, lon) members -> one realization stack."""
    mean_r = mean_da.expand_dims(realization=[0])
    if member_da is None:
        return mean_r
    members = member_da.assign_coords(realization=np.arange(1, member_da.sizes["realization"] + 1))
    return xr.concat([mean_r, members], dim="realization")


def load_submissions(paths, with_members=True):
    """paths -> {tag: {"field_value": DataArray(realization, time, lat, lon), "attrs": dict}}."""
    subs = {}
    for p in paths:
        ds = xr.open_dataset(p, decode_times=True)
        if "DATA" not in ds.data_vars:
            raise SystemExit("%s has no DATA variable (expected an ME4OH submission)" % p)
        tag = ds.attrs.get("mapped_layer") or ds.attrs.get("layer_m")
        if not tag or "_" not in str(tag):
            raise SystemExit("%s has no usable mapped_layer/layer_m attr (got %r)" % (p, tag))
        mean_da = _to_tlatlon(ds["DATA"]).astype("float64")
        members = _load_members(p) if with_members else None
        subs[str(tag)] = {"field_value": _stack(mean_da, members), "attrs": dict(ds.attrs)}
    return subs


def load_bathy(path):
    """Standard bathymetry -> DataArray(lat, lon), seafloor depth in metres, positive down.

    Reads a `depth`/`bathymetry`/`elevation` variable (or the sole 2-D variable) and orients it to
    (lat, lon). If it reads as elevation (mostly negative), it is negated to depth. The exact variable
    name and sign convention of the standard file may need adjusting here when it is finalised.
    """
    ds = xr.open_dataset(path)
    name = next((v for v in ("depth", "bathymetry", "bathy", "elevation", "z") if v in ds.data_vars), None)
    if name is None:
        two_d = [v for v in ds.data_vars if ds[v].ndim == 2]
        if len(two_d) != 1:
            raise SystemExit("can't identify the bathy variable in %s (data_vars: %s)"
                             % (path, list(ds.data_vars)))
        name = two_d[0]
    da = ds[name]
    rename = {}
    for d in da.dims:
        low = str(d).lower()
        if low.startswith("lat"):
            rename[d] = "lat"
        elif low.startswith("lon"):
            rename[d] = "lon"
    da = da.rename(rename).transpose("lat", "lon").astype("float64")
    return -da if float(da.mean()) < 0 else da


def write_blob(blob, level, cfg):
    """Write one synthetic level's dataset to NetCDF, tagged with cfg.tag and provenance link."""
    os.makedirs(cfg.out, exist_ok=True)
    blob.attrs["level"] = level.name
    blob.attrs["provenance_tag"] = cfg.tag
    if cfg.provenance_link is not None:
        blob.attrs["provenance_link"] = cfg.provenance_link
    path = os.path.join(cfg.out, "derive_%s_%s.nc" % (cfg.tag, level.name))
    blob.to_netcdf(path, engine="netcdf4")
    print("wrote", path)
    return path
