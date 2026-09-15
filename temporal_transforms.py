"""Step 4 — build the deliverables from the step-3 primitives.

`primitives` is one constituent's step-3 output: {"integral": (realization, time),
"map": (realization, time, lat, lon)}. `window` is (year0, year1) or None. Each deliverable is a
short recipe over the small helpers below:

    ohca         monthly anomaly (window baseline), then annual mean   -> (realization, year)
    ohca_absolute annual mean of the absolute integral (no demean)     -> (realization, year)
    ohu          month-to-month tendency, then annual mean             -> (realization, year)
    ohca_trend   OLS slope of the annual integral over the window      -> (realization,)
    ohu_trend    OLS slope of the annual tendency over the window      -> (realization,)
    map          per-cell monthly anomaly (window baseline)            -> (realization, time, lat, lon)

`_tendency` drops its leading step (no prior month), so `ohu` takes its annual mean with
`complete=True` — a year missing that step is NaN, not a partial average — and `_slope` skips NaN
years, keeping the dropped step out of the fit. Each trend carries a `per` attr naming its step
("year"), so packaging divides by the matching seconds-per-step.

Add a deliverable: write a recipe over the helpers and register it.
"""


def _in_window(series, dim, window):
    """Clip `series` along `dim` to `window`, an inclusive (lo, hi) pair in that axis's own terms, or
    None for the whole series. Bounds are integer years for the annual `year` axis, year strings (e.g.
    "2005") for the monthly `time` axis, which xarray reads as partial-datetime bounds.
    """
    lo, hi = window or (None, None)
    return series.sel({dim: slice(lo, hi)})


def _anomaly(series, window):
    """Subtract the mean over the window months, per realization."""
    months = None if window is None else (str(window[0]), str(window[1]))
    return series - _in_window(series, "time", months).mean("time")


def _annual(series, complete=False):
    """Calendar-year mean. With complete=True, a year missing any month is NaN instead of a partial
    mean — the treatment a differenced series needs, so its dropped leading step voids that year.
    """
    return series.groupby("time.year").mean("time", skipna=not complete)


def _tendency(series):
    """Backward month-to-month difference; the leading step is NaN (no prior month) by construction."""
    return series - series.shift(time=1)


def _slope(series, dim):
    """OLS slope of `series` against its `dim` coordinate, per realization — per one step of that
    coordinate. NaN entries are skipped: masking x to where the value exists holds the numerator and
    denominator on one valid set, so a hole can't bias the fit. Range selection is the caller's job.
    """
    x = series[dim].astype("float64").where(series.notnull())
    xc = x - x.mean(dim)
    yc = series - series.mean(dim)
    return (xc * yc).sum(dim) / (xc * xc).sum(dim)


def ohca(primitives, window):
    return _annual(_anomaly(primitives["integral"], window))


def ohca_absolute(primitives, window):
    # the ohca recipe minus the anomaly demean: the annual mean of the absolute integral. Its spread is
    # the member std of the un-demeaned value, for isolating the demean's effect on the SD from the rest.
    return _annual(primitives["integral"])


def ohu(primitives, window):
    return _annual(_tendency(primitives["integral"]), complete=True)


def ohca_trend(primitives, window):
    annual = _in_window(_annual(primitives["integral"]), "year", window)
    return _slope(annual, "year").assign_attrs(per="year")


def ohu_trend(primitives, window):
    annual = _in_window(_annual(_tendency(primitives["integral"]), complete=True), "year", window)
    return _slope(annual, "year").assign_attrs(per="year")


def gridded_anomaly(primitives, window):
    return _anomaly(primitives["map"], window)


REGISTRY = {
    "ohca": ohca,
    "ohca_absolute": ohca_absolute,
    "ohu": ohu,
    "ohca_trend": ohca_trend,
    "ohu_trend": ohu_trend,
    "map": gridded_anomaly,
}


def apply(names, maps, level, window=None):
    """Build the named deliverables for every constituent.

    -> {tag: {quantity_name: DataArray(realization, ...)}}
    """
    for name in names:
        if name not in REGISTRY:
            raise SystemExit("unknown quantity %r; known: %s" % (name, list(REGISTRY)))
    return {tag: {name: REGISTRY[name](primitives, window) for name in names}
            for tag, primitives in maps.items()}
