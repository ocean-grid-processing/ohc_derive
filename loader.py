"""Step 1 (load) and the final write.

`load_submissions` reads each native-level submission (mean field) and, unless mean-only, its member
sibling, and stacks them as `field_value` on a leading `realization` axis (index 0 = mean field, the
rest = members), so downstream steps treat every realization the same way.

`load_bathy` reads the standard bathymetry as a depth grid.

`write_blob` writes one synthetic level's dataset (each quantity plus its `_sd`) with the provenance
tag and link. `stamp_chain_provenance` rolls every upstream provenance block forward (grouped by
constituent, since derive is a fan-in) and adds this step's own `ohc_derive_*` blocks.
"""
import json
import os

import numpy as np
import xarray as xr

# This step's identity, used to namespace its provenance (`ohc_derive_run_config` / `_run_facts` /
# `_code_version`). Every step rolls all `*_run_config` / `_run_facts` / `_code_version` forward and
# adds its own; at a fan-in they're grouped by constituent, so blocks accrete without collision.
STAGE = "ohc_derive"
_PROV_SUFFIXES = ("_run_config", "_run_facts", "_code_version")


def _maybe_json(v):
    """Parse an upstream block back to JSON so it nests as a real object; leave non-JSON as-is. This is
    structural only — we never read the block's fields, so no coupling to the upstream schema."""
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return v


def _compact(obj):
    """One-line JSON — reads as a single clean line in `ncdump -h`."""
    return json.dumps(obj, separators=(",", ":"), default=str)


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
    """paths -> {tag: {"field_value": DataArray(realization, time, lat, lon), "attrs": dict}}.

    Submissions are keyed by their native-level tag, and each level a synthetic level needs is selected
    by tag — so passing the whole pool and letting each run pick its constituents is fine. But that only
    works if the pool holds exactly one file per native level: two files with the same tag (a stray
    window / experiment / rerun) is a hard error rather than a silent last-wins that would combine the
    wrong data.
    """
    subs = {}
    seen = {}
    for p in paths:
        ds = xr.open_dataset(p, decode_times=True)
        if "DATA" not in ds.data_vars:
            raise SystemExit("%s has no DATA variable (expected an ME4OH submission)" % p)
        tag = ds.attrs.get("mapped_layer") or ds.attrs.get("layer_m")
        if not tag or "_" not in str(tag):
            raise SystemExit("%s has no usable mapped_layer/layer_m attr (got %r)" % (p, tag))
        tag = str(tag)
        if tag in seen:
            raise SystemExit("two submissions map to native level %s:\n  %s\n  %s\n"
                             "the pool must hold exactly one file per native level." % (tag, seen[tag], p))
        seen[tag] = p
        mean_da = _to_tlatlon(ds["DATA"]).astype("float64")
        members = _load_members(p) if with_members else None
        subs[tag] = {"field_value": _stack(mean_da, members), "attrs": dict(ds.attrs)}
    return subs


def load_bathy(path):
    """The standard bathymetry (etopo60.cdf) -> DataArray(lat, lon), seafloor depth in metres.

    This is the same file ohc_ingest pins the mapping grid to: relief variable ROSE (metres, negative
    below sea level) on dims ETOPO60Y (latitude) and ETOPO60X (longitude), row-major [lat, lon]. We
    read it as-is, so lat/lon come out in the mapping-grid order the submissions also carry, and negate
    the relief to positive-down depth to match ingest's seabed convention.
    """
    da = xr.open_dataset(path)["ROSE"]
    da = da.rename({"ETOPO60Y": "lat", "ETOPO60X": "lon"}).transpose("lat", "lon").astype("float64")
    return -da


def stamp_chain_provenance(blob, level, cfg, submissions):
    """Roll the upstream provenance chain forward and add this step's own blocks.

    derive is a fan-in: N constituents each carry their own `*_run_config` / `_run_facts` /
    `_code_version` (localgp_ingest_*, localgp_publish_*, …). We group each block by the constituent it
    came from — `<block> = {constituent_tag: block}` — so nothing is deduplicated away and downstream
    never has to know who produced what. Blocks are opaque: parsed only to nest cleanly, never read.
    """
    contributors = [c.tag for c in level.contributors]
    forwarded = {}                                            # block_name -> {constituent_tag: block}
    for tag in contributors:
        for k, v in submissions[tag]["attrs"].items():
            if k.endswith(_PROV_SUFFIXES):
                forwarded.setdefault(k, {})[tag] = _maybe_json(v)
    for block_name, per_constituent in forwarded.items():
        blob.attrs[block_name] = _compact(per_constituent)

    require_top = cfg.require_top if cfg.require_top is not None else level.require_top
    blob.attrs["%s_code_version" % STAGE] = cfg.code_version
    blob.attrs["%s_run_config" % STAGE] = _compact(vars(cfg))
    blob.attrs["%s_run_facts" % STAGE] = _compact({
        "level": level.name,
        "quantities": cfg.quantities,
        "mask": cfg.mask,
        "require_top": require_top,
        "time_window": "%d-%d" % cfg.time_window if cfg.time_window else "all",
        "ensemble": not cfg.no_ensemble,
        "area_m2": blob.attrs.get("area_m2"),
        "volume_m3": blob.attrs.get("volume_m3"),
        "constituents": contributors,
        "n_fac": {c.tag: c.n_fac for c in level.contributors},
        "cp0": blob.attrs.get("cp0"),
        "rho0": blob.attrs.get("rho0"),
    })


def _record_span(blob):
    """(year0, year1) spanned by the blob's own axis — `year` for the annual quantities, `time` for the
    gridded/monthly ones — or None if it carries neither (e.g. a trend-only blob)."""
    if "year" in blob.coords:
        yrs = blob["year"].values.astype(int)
        return int(yrs.min()), int(yrs.max())
    if "time" in blob.coords:
        yrs = blob["time"].values.astype("datetime64[Y]").astype(int) + 1970
        return int(yrs.min()), int(yrs.max())
    return None


def _window_token(cfg, blob):
    """Filename year-range token: the `--time-window` if given, else the blob's own full record span
    (so a windowless run reads as its actual years, not a bare `all`)."""
    if cfg.time_window:
        return "%d_%d" % cfg.time_window
    span = _record_span(blob)
    return "%d_%d" % span if span else "all"


def window_token(cfg, submissions):
    """The same filename year-range token, resolved from the submissions' time axis — so the mask/
    coverage auxiliaries (written before the blob exists) share the main file's window token."""
    if cfg.time_window:
        return "%d_%d" % cfg.time_window
    for s in submissions.values():
        t = s["field_value"]["time"].values
        if t.size:
            yrs = t.astype("datetime64[Y]").astype(int) + 1970
            return "%d_%d" % (int(yrs.min()), int(yrs.max()))
    return "all"


def write_blob(blob, level, cfg, window=None):
    """Write one synthetic level's dataset to NetCDF, tagged with cfg.tag and provenance link."""
    os.makedirs(cfg.out, exist_ok=True)
    blob.attrs["level"] = level.name
    # The attr keeps its intent semantics ("all" = whole-record baseline) — the gcos emitter reads it to
    # reject a windowless derive. The filename gets a concrete year range so different windows can't
    # collide (whole-record vs 2005-2024 are the same tag+level, different content).
    blob.attrs["time_window"] = "%d-%d" % cfg.time_window if cfg.time_window else "all"
    blob.attrs["provenance_tag"] = cfg.tag
    if cfg.provenance_link is not None:
        blob.attrs["provenance_link"] = cfg.provenance_link
    win = window if window is not None else _window_token(cfg, blob)
    path = os.path.join(cfg.out, "derive_%s_%s_%s.nc" % (cfg.tag, win, level.name))
    blob.to_netcdf(path, engine="netcdf4")
    print("wrote", path)
    return path
