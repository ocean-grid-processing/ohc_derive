# ohc_derive

`ohc_derive` does the per-product downstream math on one `ohc_ingest` submission — anomalies, trends, integrals — with no reference to any other product (cross-group comparison is `me4oh_assess`'s job). It's the missing middle of the pipeline:

```
ohc_ingest ──▶ ohc_derive ──▶ ohc_combine / me4oh_assess
(one product's  (per-product      (combine layers /
 OHC store)      derived fields)    compare products)
```

## What it computes

**Input** is `ohc_ingest`'s published `OHC_` submission (posterior-mean OHC, TJ/m², mask already applied as NaN) — the `.nc` handoff, not the internal zarr. With the ensemble on, it also reads the `OHCENS_` sibling (from `publish.py --ensemble`, located by swapping the filename prefix). `cell_area` is regenerated from the grid, so nothing else is needed upstream.

A **product** is that submission loaded as an `xr.Dataset`: the mean OHC field (and the full ensemble when present), plus `cell_area` and a `usable` mask (finite at every timestep).

A **transform** is a pure `f(field, product) -> Dataset` that reduces over time and broadcasts over leading dims — so the *same* `f` runs on the mean field `[time,lat,lon]` and on the ensemble `[member,time,lat,lon]`. That uniformity is what lets the **ensemble wrapper** produce, automatically, a central estimate (from the mean field) plus a `_sd` companion (1σ across the 100 members) for any transform. The registry:

| `--transforms` name | output variable(s) | dims | units | `_sd`? | what it is |
|---|---|---|---|:--:|---|
| `timemean` | `ohc_timemean` | (lat, lon) | TJ/m² | yes | mean over time |
| `trend` | `ohc_trend` | (lat, lon) | TJ/m²/s | yes | linear OLS slope, per second, on a uniform-month axis |
| `integral` | `ohc_integral` | (time,) | TJ | yes | area-weighted horizontal integral |
| `anomaly` | `ohc_anom` + `ohc_anom12` | (time,lat,lon) + (month,lat,lon) | TJ/m² | yes | deseasonalized+detrended anomaly, and the seasonal cycle |
| `area` | `area_total` | () scalar | m² | no | usable ocean area (pure grid geometry) |

The runner merges the selected transforms into one mixed-rank Dataset and writes `derive_<product>_<period>_lev<low>_<high>.nc`. The exact definitions, the MATLAB-parity notes (why the trend uses uniform-month seconds, how `anom`/`anom12` are built), and the provenance attributes are in [`derive_schema.md`](derive_schema.md).

## Usage

### Environment

```bash
pip install -r requirements.txt          # numpy, xarray>=2024.10, netCDF4
```

### Test

Synthetic fields with known analytic answers — no real data, no cluster:

```bash
pip install -r requirements.txt -r requirements-dev.txt   # adds pytest
pytest                                                    # from this directory
```

Covers transforms vs. analytic expectations (constant/linear/seasonal), the ensemble wrapper (central from the mean, `_sd` from member spread, single-member → NaN), the loader's `.nc` round-trip + sibling resolution, and the CLI end-to-end (all transforms, `--no-ensemble`, unknown-transform error).

### Run

```bash
# everything, with ensemble uncertainty (needs the OHCENS_ sibling next to the submission):
python derive.py /path/OHC_<...>.nc --transforms all --out derive/

# a subset, central-only — fast, no OHCENS_ needed (this is what ohc_combine calls):
python derive.py /path/OHC_<...>.nc --transforms integral,area --no-ensemble --out derive/
```

With the ensemble on (the default), the `OHCENS_` sibling **must** exist next to the submission or the loader raises `FileNotFoundError`, and every transform except `area` gets a `_sd`. `anomaly`'s `_sd` is the heaviest — its per-member form is a full `(member, time, lat, lon)` stack (~7 GB transient, ~20 GB peak), so run the ensemble path inside your job allocation. `--no-ensemble` is the fast central-only path; central values are byte-identical either way. The output group attr `ensemble` records `1`/`0`.

#### derive.py options

All configuration is on the command line — no env, no config file. The available transforms are the registry in [`transforms.py`](transforms.py) (`transforms.REGISTRY`).

| option | default | effect |
|---|---|---|
| `SUBMISSION.nc` (positional) | *(required)* | the `OHC_` submission from `ohc_ingest`'s `publish.py` (posterior-mean OHC, TJ/m², mask applied as NaN). |
| `--transforms` | `all` | comma list of `timemean,trend,integral,anomaly,area`, or `all`. Unknown names error. |
| `--no-ensemble` | off (ensemble **on**) | central estimate only — skip the `_sd` companions and do **not** read the `OHCENS_` sibling. |
| `--out` | `.` | output directory. |

## Adding a transform

Write `f(field, product) -> Dataset` that reduces over `time` (and broadcasts over any leading dim), give its output variables `units`/`long_name`, and register it in `transforms.REGISTRY` with an `ensemble` flag. The wrapper and runner do the rest — no other file changes.
