"""Step 2 — cross-layer masking, pluggable.

A prescription takes the synthetic level, its constituents (each with a `field_value` stack and dbar
bounds), and the standard bathy, and returns the masked constituents plus the footprint mask:

    (masked, footprint)
    masked    = {tag: {"field_value": DataArray(realization, time, lat, lon), "n_fac": int}}
    footprint = DataArray(lat, lon) bool, True where the level holds water (the cells the area counts)

`apply` runs the named prescription, dumps the footprint to a png, and returns `(masked, area_m2)`,
the summed cell area of the footprint — ocean where the level has water, so land and dropped columns
don't inflate the per-area densities downstream.

Default `fully_wet_nan`, per cell and per constituent:
  * a cell drops out of the level where any fully-wet constituent is undefined (NaN in the mean or
    any member, at any time);
  * a constituent contributes its value where it is not dry and defined everywhere, and 0 otherwise;
  * the footprint is the cells with a contribution left after the drops (the shallowest wet area minus
    the dropped columns); land and dry shelves contribute nothing and are not in it.

Add a prescription: write `(level, constituents, reference_bathy) -> (masked, footprint)` and register it.
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
        arr[:, :, ~contributes[c["tag"]] & ~exclude] = 0.0  # in grid, not this level's water
        arr[:, :, exclude] = np.nan                         # dropped cells
        field_value = xr.DataArray(arr, dims=c["field_value"].dims, coords=c["field_value"].coords)
        masked[c["tag"]] = {"field_value": field_value, "n_fac": c["n_fac"]}

    # the footprint: cells that still hold water for this level (any constituent contributes, not dropped)
    any_contributes = np.zeros((nlat, nlon), dtype=bool)
    for c in constituents:
        any_contributes |= contributes[c["tag"]]
    footprint = any_contributes & ~exclude
    return masked, xr.DataArray(footprint, dims=("lat", "lon"), coords={"lat": lat, "lon": lon})


REGISTRY = {
    "fully_wet_nan": fully_wet_nan,
}


def apply(name, level, constituents, reference_bathy, out_dir="."):
    """Run the named prescription, dump its footprint png, return (masked, footprint area in m^2)."""
    if name not in REGISTRY:
        raise SystemExit("unknown mask prescription %r; known: %s" % (name, list(REGISTRY)))
    masked, footprint = REGISTRY[name](level, constituents, reference_bathy)
    _dump_png(footprint, reference_bathy, level.name, name, out_dir)
    area = grid.cell_area(footprint["lat"].values, footprint["lon"].values)
    return masked, float(area.where(footprint).sum())


def _dump_png(footprint, reference_bathy, level_name, mask_name, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap
        from matplotlib.patches import Patch
    except Exception:
        return
    # three classes: in the footprint (white), ocean outside it (black), land (grey, from the bathy)
    category = np.where(footprint.values, 1, 0)            # 1 in footprint, 0 outside
    category[reference_bathy.values < 0] = 2               # negative depth = above sea level -> land
    cmap = ListedColormap(["black", "white", "lightgrey"])

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.pcolormesh(footprint["lon"], footprint["lat"], category, shading="auto",
                  cmap=cmap, vmin=-0.5, vmax=2.5)
    ax.set_title("%s footprint (%s)" % (level_name, mask_name))
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
    ax.legend(handles=[Patch(facecolor="white", edgecolor="grey", label="in footprint"),
                       Patch(facecolor="black", label="outside footprint"),
                       Patch(facecolor="lightgrey", label="land")],
              loc="lower left", fontsize=8, framealpha=0.9)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "mask_%s_%s.png" % (level_name, mask_name))
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print("wrote", path)
