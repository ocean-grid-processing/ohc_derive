# ohc_derive

`ohc_derive` does per-product downstream math — anomalies, trends, integrals — on a single ME4OH-compliant OHC submission, writing the derived fields as one NetCDF per layer.

## What it computes

**Input** is an ME4OH-compliant `OHC_` submission NetCDF — posterior-mean OHC, TJ/m², mask already applied as NaN. If an `OHCENS_` sibling (the full per-member ensemble, same filename with the prefix swapped) sits next to it, ensemble uncertainty is available too. `cell_area` is regenerated from the grid, so the submission is all that's needed.

A **product** is that submission loaded as an `xr.Dataset`: the mean OHC field (and the full ensemble when present), plus `cell_area` and a `usable` mask (finite at every timestep).

A **transform** is a pure function `f(field, product) -> Dataset`. It addresses the field by **dimension name** (`time`, `lat`, `lon`) rather than axis position — some collapse `time` into a map, `integral` collapses `lat`/`lon` into a series, `anomaly` regroups `time` into a seasonal `month` axis (see the table). Because nothing is pinned to an axis position, the *same* `f` runs unchanged whether the field is the mean `(time, lat, lon)` or the ensemble `(member, time, lat, lon)`: the extra leading `member` axis just rides along, and the operation runs once per member. The **ensemble wrapper** uses exactly that — it runs a transform on the mean field for the central estimate and on the ensemble for the spread, collapsing `member` into a `_sd` companion (1σ across the 100 members). No transform carries any ensemble-specific code. The registry:

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

Described in `Dockerfile` to generate a containerized environment; make a similar env in anaconda on blanca when running on the cluster.

### Test

Tests can be run on your machine in the containerized environment:

```
docker image build -t ohc_derive:test .
docker container run -v $(pwd):/app ohc_derive:test pytest
```

### Run

See `derive.slurm` for a real example of running this on blanca at CU.

With the ensemble on (the default), the `OHCENS_` sibling **must** exist next to the submission or the loader raises `FileNotFoundError`, and every ensemble transform (all but `area`) gets a collapsed `<var>_sd`. Naming a transform in `--keep-members` instead outputs its **raw members** as `<var>_ens` (XOR with `_sd`) — for a consumer that reduces the ensemble itself *after* a later nonlinear step (the spread of a yearly mean, say, which the collapsed `_sd` can't give). Memory is the caller's call: `anomaly`'s per-member form is a full `(member, time, lat, lon)` stack (~7 GB transient, ~20 GB peak), so run any ensemble path inside your job allocation. `--no-ensemble` is the fast central-only path; central values are byte-identical either way. Group attrs `ensemble` (`1`/`0`) and `members_kept` record what was done.

#### derive.py options

All configuration is on the command line — no env, no config file. The available transforms are the registry in [`transforms.py`](transforms.py) (`transforms.REGISTRY`).

| option | default | effect |
|---|---|---|
| `SUBMISSION.nc` (positional) | *(required)* | a published `OHC_` submission NetCDF (posterior-mean OHC, TJ/m², mask applied as NaN). |
| `--transforms` | `all` | comma list of `timemean,trend,integral,anomaly,area`, or `all`. Unknown names error. |
| `--no-ensemble` | off (ensemble **on**) | central estimate only — skip the `_sd` companions and do **not** read the `OHCENS_` sibling. |
| `--keep-members` | *(none)* | comma list of transforms (or `all`) to output as raw members `<var>_ens` instead of the collapsed `<var>_sd` (XOR). Ensemble transforms only, and must be among `--transforms`; anything else (incl. with `--no-ensemble`) errors. |
| `--out` | `.` | output directory. |

## Adding a transform

Write `f(field, product) -> Dataset` that addresses the field by dimension name (so it stays agnostic to the leading `member` axis), give its output variables `units`/`long_name`, and register it in `transforms.REGISTRY` with an `ensemble` flag. The wrapper and runner do the rest — no other file changes.
