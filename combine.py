"""Step 5 (collapse) and step 6 (combine).

Step 5 — collapse. Per constituent, per quantity, split the `realization` axis:
    value = the quantity at realization 0 (the mean field)
    sd    = standard deviation (ddof=1) across the member realizations, or None if mean-only

    collapse_sd({tag: {q: DataArray(realization, ...)}}) -> {tag: {q: {"value":..., "sd":...}}}

Step 6 — combine. Fold the constituents into the synthetic level:
    value(q) = sum_i n_fac_i * value_i(q)
    sd(q)    = sum_i n_fac_i * sd_i(q)      worst-case, summed after the collapse
into one dataset per level: each `q` and `q_sd`, plus the footprint area/volume (both from the mask
step) and the physical constants as attributes. Packaging turns the extensive quantities into per-area
densities from these.
"""
import xarray as xr


def _split(da):
    """Central value from the mean field; standard deviation across the members (or None)."""
    value = da.isel(realization=0, drop=True)
    members = da.isel(realization=slice(1, None))
    sd = members.std("realization", ddof=1) if members.sizes["realization"] else None
    return {"value": value, "sd": sd}


def collapse_sd(series):
    """See step 5. -> {tag: {quantity: {"value": DataArray, "sd": DataArray or None}}}."""
    return {tag: {name: _split(da) for name, da in quantities.items()}
            for tag, quantities in series.items()}


def _nfac_sum(per_constituent, contributors, quantity, key):
    """n_fac-weighted sum of one quantity's `value` (or `sd`) across constituents; None if any is None."""
    parts = [per_constituent[c.tag][quantity][key] for c in contributors]
    if any(p is None for p in parts):
        return None
    terms = [c.n_fac * p for c, p in zip(contributors, parts)]
    return sum(terms[1:], terms[0])


def combine_synthetic(per_constituent, level, area_m2, volume_m3, constants):
    """See step 6. -> xr.Dataset for one synthetic level. Area and volume come from the mask step."""
    contributors = level.contributors
    quantities = per_constituent[contributors[0].tag]        # same quantity set for every constituent

    data = {}
    for q in quantities:
        data[q] = _nfac_sum(per_constituent, contributors, q, "value")
        # arithmetic drops attrs; carry the quantity's own metadata (e.g. a trend's `per`) from a source
        data[q].attrs = dict(per_constituent[contributors[0].tag][q]["value"].attrs)
        sd = _nfac_sum(per_constituent, contributors, q, "sd")
        if sd is not None:
            data[q + "_sd"] = sd

    blob = xr.Dataset(data)
    blob.attrs["level"] = level.name
    blob.attrs["area_m2"] = area_m2
    blob.attrs["volume_m3"] = volume_m3
    blob.attrs.update(constants)                              # cp0, rho0 (if the submissions carried them)
    return blob
