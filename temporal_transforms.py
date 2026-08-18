"""Step 4 — build the deliverables from the step-3 primitives.

`primitives` is one constituent's step-3 output: {"integral": (realization, time),
"map": (realization, time, lat, lon)}. `window` is (year0, year1) or None. Each deliverable is a
one-line recipe over the small helpers below:

    ohca         monthly anomaly (window baseline), then annual mean   -> (realization, year)
    ohu          month-to-month tendency, then annual mean             -> (realization, year)
    ohca_trend   OLS slope of the annual integral over the window      -> (realization,)
    ohu_trend    OLS slope of the annual tendency over the window      -> (realization,)
    map          per-cell monthly anomaly (window baseline)            -> (realization, time, lat, lon)

Add a deliverable: write a recipe over the helpers and register it.
"""


def _in_window(series, window):
    """The months whose year falls in the window; None -> the whole series."""
    if window is None:
        return series
    y0, y1 = window
    return series.sel(time=(series["time.year"] >= y0) & (series["time.year"] <= y1))


def _anomaly(series, window):
    """Subtract the mean over the window months, per realization."""
    return series - _in_window(series, window).mean("time")


def _annual(series):
    """Calendar-year mean."""
    return series.groupby("time.year").mean("time")


def _tendency(series):
    """Backward month-to-month difference; NaN at the first step."""
    return series - series.shift(time=1)


def _slope(annual, window):
    """OLS slope of an annual series over the window years, per realization."""
    if window is not None:
        y0, y1 = window
        annual = annual.sel(year=(annual["year"] >= y0) & (annual["year"] <= y1))
    x = annual["year"].astype("float64")
    xc = x - x.mean()
    return (xc * (annual - annual.mean("year"))).sum("year") / (xc * xc).sum("year")


def ohca(primitives, window):        return _annual(_anomaly(primitives["integral"], window))
def ohu(primitives, window):         return _annual(_tendency(primitives["integral"]))
def ohca_trend(primitives, window):  return _slope(_annual(primitives["integral"]), window)
def ohu_trend(primitives, window):   return _slope(_annual(_tendency(primitives["integral"])), window)
def gridded_anomaly(primitives, window):  return _anomaly(primitives["map"], window)


REGISTRY = {
    "ohca": ohca,
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
