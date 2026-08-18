"""Step 2 — cross-layer masking, pluggable.

A prescription takes the synthetic level, its constituents (each with a `field_value` stack and dbar
bounds), and the standard bathy, and returns the masked constituents plus the excluded-cell mask:

    (masked, exclude)
    masked  = {tag: {"field_value": DataArray(realization, time, lat, lon), "n_fac": int}}
    exclude = DataArray(lat, lon) bool, True where the cell drops out of the synthetic level

`apply` runs the named prescription, dumps the footprint to a png, and returns `(masked, area_m2)`
(the summed cell area of the included cells).

Default `fully_wet_nan`, per cell and per constituent:
  * a cell drops out of the level where any fully-wet constituent is undefined (NaN in the mean or
    any member, at any time);
  * a constituent contributes its value where it is not dry and defined everywhere, and 0 otherwise.

Add a prescription: write `(level, constituents, reference_bathy) -> (masked, exclude)` and register it.
"""
import os

import numpy as np
import xarray as xr

import grid


def fully_wet_nan(level, constituents, reference_bathy):
    lat, lon = reference_bathy["lat"], reference_bathy["lon"]
    floor = reference_bathy.values                          # seafloor depth, metres
    nlat, nlon = lat.size, lon.size

    # the one whole-cube reduction: is each cell finite across every member and time step?
    defined = {c["tag"]: c["field_value"].notnull().all(("time", "realization")).values
               for c in constituents}

    exclude = np.zeros((nlat, nlon), dtype=bool)            # cell drops out of the level
    contributes = {c["tag"]: np.zeros((nlat, nlon), dtype=bool) for c in constituents}

    for i in range(nlat):
        for j in range(nlon):
            for c in constituents:
                wet = floor[i, j] >= c["bottom"]            # layer sits entirely above the floor
                dry = np.isnan(floor[i, j]) or floor[i, j] < c["top"]   # entirely below it
                if wet and not defined[c["tag"]][i, j]:
                    exclude[i, j] = True                    # a wet gap kills the column
                elif not dry and defined[c["tag"]][i, j]:
                    contributes[c["tag"]][i, j] = True      # else this cell is a 0 for this level

    masked = {}
    for c in constituents:
        arr = c["field_value"].values.copy()
        arr[:, :, ~contributes[c["tag"]] & ~exclude] = 0.0  # in-footprint, not this level's water
        arr[:, :, exclude] = np.nan                         # dropped cells
        field_value = xr.DataArray(arr, dims=c["field_value"].dims, coords=c["field_value"].coords)
        masked[c["tag"]] = {"field_value": field_value, "n_fac": c["n_fac"]}
    return masked, xr.DataArray(exclude, dims=("lat", "lon"), coords={"lat": lat, "lon": lon})


REGISTRY = {
    "fully_wet_nan": fully_wet_nan,
}


def apply(name, level, constituents, reference_bathy, out_dir="."):
    """Run the named prescription, dump its footprint png, return (masked, footprint area in m^2)."""
    if name not in REGISTRY:
        raise SystemExit("unknown mask prescription %r; known: %s" % (name, list(REGISTRY)))
    masked, exclude = REGISTRY[name](level, constituents, reference_bathy)
    _dump_png(exclude, level.name, name, out_dir)
    area = grid.cell_area(exclude["lat"].values, exclude["lon"].values)
    return masked, float(area.where(~exclude).sum())


def _dump_png(exclude, level_name, mask_name, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    include = (~exclude).astype("int8")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.pcolormesh(include["lon"], include["lat"], include, shading="auto", cmap="Greys_r")
    ax.set_title("%s footprint (%s)" % (level_name, mask_name))
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "mask_%s_%s.png" % (level_name, mask_name))
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print("wrote", path)
