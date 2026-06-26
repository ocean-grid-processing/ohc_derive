# ohc_derive

Per-product downstream calculations on `ohc_ingest` output — the single-product "grind", as
opposed to the cross-group comparison in `me4oh_assess`. It takes **one** product's OHC store
and derives new quantities from it (anomalies, trends, integrals, …) with no reference to any
other product. It is the missing middle of the pipeline:

```
ohc_ingest  ──▶  ohc_derive  ──▶  me4oh_assess
(produce one     (per-product       (compare products)
 product's OHC)   derived fields)
```

## Model

Input is `ohc_ingest`'s **published NetCDF** (the handoff format — not the internal zarr): the
`OHC_` submission (posterior-mean OHC, TJ/m², mask already applied as NaN). Ensemble uncertainty
additionally reads the `OHCENS_` sibling from `publish.py --ensemble`, located by swapping the
filename prefix. `cell_area` is regenerated from the grid (a pure function), so nothing else is
needed from upstream.

A **product** is loaded as an xr.Dataset with the OHC field as the posterior mean (and the full
ensemble, when present), plus `cell_area` and the `usable` mask (finite at every timestep).

A **transform** is a pure function `f(field, product) -> Dataset` that reduces/operates over
time and broadcasts over leading dims — so the same `f` works on the mean field
`[time,lat,lon]` and on the ensemble `[member,time,lat,lon]`. That uniformity is what lets the
**ensemble wrapper** compute a central estimate (from the mean field) and a `_sd` companion
(spread across members) for any transform, automatically.

The **runner** selects transforms, merges their outputs into one Dataset (variables of mixed
rank sharing coordinates), and writes one NetCDF per product/layer. See
[`derive_schema.md`](derive_schema.md) for the output variables and conventions.

```
ohc_derive/
  loader.py      load_product(store, preset) -> product Dataset
  transforms.py  the f(field, product) registry (timemean, trend, integral, anomaly, area)
  ensemble.py    with_uncertainty(f, product): central from mean field, _sd from ensemble
  derive.py      CLI entry: select transforms, merge, write  (run: python derive.py ...)
```

## Run

```bash
pip install -r requirements.txt   # numpy, xarray>=2024.10, netCDF4

# all transforms, ensemble uncertainty on (needs the OHCENS_ sibling):
python derive.py /path/OHC_<...>.nc --transforms all --out derive/

# a subset, central estimate only (fast, no OHCENS_ needed):
python derive.py /path/OHC_<...>.nc --transforms trend,integral --no-ensemble --out derive/
```

Output: `derive/derive_<product>_<period>_lev<low>_<high>.nc` — e.g. `ohc_timemean`/`_sd`
(maps), `ohc_trend`/`_sd` (maps), `ohc_integral`/`_sd` (series), `ohc_anom` (cube), `ohc_anom12`
(climatology), `area_total` (scalar), all in one file.

## Adding a transform

Write `f(field, product) -> Dataset` that reduces over `time` (and broadcasts over any leading
dim), give its output variables `units`/`long_name`, and register it in `transforms.REGISTRY`
with an `ensemble` flag. The wrapper and runner handle the rest. No other file changes.

## Status / notes

First pass. Ensemble-propagated: `timemean`, `trend`, `integral` (cheap per-member reductions).
Not yet ensemble-propagated: `anomaly` (its per-member form is a full `(member,time,lat,lon)`
cube ~7 GB — deferred to a separate member-retaining export). Reads the full ensemble for the
`_sd` companions, so run inside the job allocation.
