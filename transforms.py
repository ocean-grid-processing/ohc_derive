"""The derive transforms: f(field, product) -> xr.Dataset.

Each transform reduces/operates over the time axis and broadcasts over any leading dims, so the
*same* function works on the posterior-mean field [time,lat,lon] and on the ensemble
[member,time,lat,lon] (the ensemble wrapper relies on that). Transforms are pure; they read
`product` only for ancillaries (cell_area, usable). REGISTRY maps a name to (fn, ensemble_flag);
ensemble_flag=True means "also propagate uncertainty through the ensemble".

Output shapes span the vocabulary: maps (lat,lon), a series (time), a cube (time,lat,lon), a
climatology (month,lat,lon), and a scalar (0-d) — all variables in one Dataset, sharing coords.
"""
import numpy as np
import xarray as xr


# Idealized uniform month length, matching the original MATLAB
# (helper_compute_trend_per_second_from_monthly: t = (0:n-1)*365.25/12*86400).
SEC_PER_MONTH = 365.25 / 12.0 * 24.0 * 3600.0


def _time_seconds(field):
    """Uniform monthly seconds (the MATLAB convention), not real calendar spacing.

    The trend's slope is per-second on this axis, and the anomaly's linear detrend uses the same
    evenly-spaced {1, t} subspace as MATLAB's index-based `detrend`. Real day-15 spacing would
    shift the slope and the residual slightly off the original.
    """
    n = field.sizes["time"]
    sec = np.arange(n, dtype="float64") * SEC_PER_MONTH
    return xr.DataArray(sec, dims=("time",), coords={"time": field["time"]})


def _slope_per_s(field):
    """Least-squares linear slope over time (units of field per second)."""
    t = _time_seconds(field)
    tc = t - t.mean()
    yc = field - field.mean("time")
    return (tc * yc).sum("time") / (tc * tc).sum()   # reduces time, keeps other dims


def time_mean(field, product):
    """Map: time-mean OHC."""
    m = field.mean("time")
    m.attrs = {"units": "TJ/m2", "long_name": "time-mean ocean heat content density"}
    return xr.Dataset({"ohc_timemean": m})


def trend(field, product):
    """Map: linear OHC trend per second."""
    s = _slope_per_s(field).where(product["usable"])
    s.attrs = {"units": "TJ/m2/s", "long_name": "linear OHC trend"}   # field is TJ/m^2, slope per second
    return xr.Dataset({"ohc_trend": s})


def _integrate(field, product):
    """Area-weighted horizontal integral of OHC -> series [..., time] in TJ (NaN cells drop out)."""
    return (field * product["cell_area"]).sum(("lat", "lon"))


def integral(field, product):
    """Series: area-weighted global integral of OHC (TJ = TJ/m^2 field x m^2 cell area)."""
    series = _integrate(field, product)
    series.attrs = {"units": "TJ", "long_name": "area-integrated ocean heat content"}
    return xr.Dataset({"ohc_integral": series})


def integral_anom(field, product):
    """Series: area-integrated OHC anomaly, all-time mean removed (OHCA), TJ.

    Canonical, parameter-free referencing — the baseline is the whole-record mean. A deliverable
    that wants a specific baseline *window* (e.g. GCOS's 2005-2024) re-references this downstream;
    derive only provides the canonical form. Because integration is linear and the mask is
    time-constant, this is exactly `integral` with its own time-mean subtracted.
    """
    anom = _integrate(field, product)
    anom = anom - anom.mean("time")
    anom.attrs = {"units": "TJ", "long_name": "area-integrated OHC anomaly (all-time mean removed)"}
    return xr.Dataset({"ohc_integral_anom": anom})


def integral_tendency(field, product):
    """Series: month-to-month change in area-integrated OHC (ocean heat uptake), TJ.

    Backward first difference on the full `time` axis with the first step NaN (no prior month) —
    prior-art convention, so it stays aligned month-for-month with the other series:
    `tendency(t) = integral(t) - integral(t-1)`, `tendency(t0) = NaN`. Matches the original's
    `data_tendency` (MATLAB `diff(bfr_tseries)`): the raw change per monthly step, NOT normalized
    by dt. A per-second uptake flux (W/m^2) is a downstream units choice, not baked in here.
    """
    series = _integrate(field, product)
    tend = series - series.shift(time=1)                    # backward diff; t0 -> NaN, full axis kept
    tend.attrs = {"units": "TJ", "long_name": "area-integrated OHC tendency (month-to-month change)"}
    return xr.Dataset({"ohc_integral_tendency": tend})


def anomaly(field, product):
    """Cube + climatology: deseasonalized+detrended anomaly and the seasonal cycle.

    Mirrors helper_compute_mean_trendpersecond_anom12_anom_from_monthly.m: build the monthly
    climatology, anom12 = climatology - overall mean, deseason = field - climatology[month], then
    linear-detrend the deseasonalized field. (`groupby("time.month")` bins by calendar month,
    identical to the MATLAB position-mod-12 binning for January-start records, which is our case.)
    """
    clim = field.groupby("time.month").mean("time")              # [month, lat, lon]
    anom12 = clim - field.mean("time")
    anom12.attrs = {"units": "TJ/m2", "long_name": "seasonal climatology anomaly"}

    deseason = field.groupby("time.month") - clim               # [time, lat, lon]
    t = _time_seconds(field)
    tc = t - t.mean()
    slope = (tc * deseason).sum("time") / (tc * tc).sum()
    anom = (deseason - slope * tc).where(product["usable"])
    anom = anom - anom.mean("time")                             # center on zero
    anom.attrs = {"units": "TJ/m2", "long_name": "deseasonalized, detrended OHC anomaly"}
    return xr.Dataset({"ohc_anom": anom, "ohc_anom12": anom12})


def area(field, product):
    """Scalar (0-d): total usable ocean area."""
    a = product["cell_area"].where(product["usable"]).sum()
    a.attrs = {"units": "m2", "long_name": "total usable ocean area"}
    return xr.Dataset({"area_total": a})


# name -> (fn, ensemble_propagated)
REGISTRY = {
    "timemean": (time_mean, True),
    "trend": (trend, True),
    "integral": (integral, True),
    "integral_anom": (integral_anom, True),         # OHCA series; cheap (member, time) ensemble
    "integral_tendency": (integral_tendency, True), # OHU series; cheap; backward diff on time (NaN at t0)
    "anomaly": (anomaly, True),    # cube output; higher transient memory (~7 GB member stack)
    "area": (area, False),         # pure grid geometry; no uncertainty to propagate
}
