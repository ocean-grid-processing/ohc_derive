# ohc_derive

`ohc_derive` builds combined-level ("synthetic-level") ocean-heat-content analysis quantities — OHCA, OHU, their trends, and gridded anomaly maps — from native-level ME4OH submissions and a standard bathymetry, writing one NetCDF per synthetic level. It works from any ME4OH-compliant submissions plus a standard bathy, so it is not tied to a single producer.

## What it computes

**Inputs** are the native-level `OHC_` submission NetCDFs that make up a synthetic level — its *constituents* — plus a standard bathymetry on the common grid. Each `OHC_` file is the posterior-mean field; if its `OHCENS_` sibling (same name, `OHC_` swapped for `OHCENS_`) sits alongside, the per-member ensemble is loaded too. `cell_area` is regenerated from the grid.

A **synthetic level** is an `n_fac`-weighted sum of native ME4OH levels, shallowest first — for example `0_2000` is `15_20`(×3) + `15_300` + `300_700` + `700_1850` + `1800_1850`(×3). `n_fac` scales a thin measured layer up to the slab it stands in for; each constituent carries its own dbar `top`/`bottom`, used against the bathy in the mask. The level table lives in [`levels.py`](levels.py) (`levels.LEVELS`): `0_300`, `0_700`, `0_1000`, `700_2000`, `0_2000`.

One run builds one synthetic level (`--level`), so levels parallelize across jobs. It proceeds in six steps:

1. **load** — read the constituents' submissions (mean field + members) and the standard bathy.
2. **mask** — apply the cross-layer mask prescription over the constituents.
3. **primitives** — reduce each constituent to its map-level primitives: the area-weighted `integral` (a time series) and the gridded field (`map`).
4. **build** — compose the primitives into the requested deliverables.
5. **collapse** — per constituent, take the central value from the mean field and the 1σ spread across the members.
6. **combine** — `n_fac` sum the constituents into the synthetic level: values linearly, standard deviations worst-case.

The mean field and its members ride together on a leading `realization` axis (index 0 is the mean field, the rest are members). Steps 3–4 transform every realization the same way, and step 5 reads the central value off index 0 and the spread off the members. So an anomaly demean along time hits every realization, and each member is referenced to its own window mean.

### Masking

Cross-layer masking is pluggable (`masks.REGISTRY`); each prescription returns the masked constituents, a footprint (the cells counted for area), and a per-cell column height (metres). `apply` turns those into the level's `area_m2` (footprint cell area) and `volume_m3` (the cell-area-weighted sum of the height), so the volume tapers with the kept column rather than assuming a slab. Alongside, it writes `mask_<level>_<mask>.png` (the footprint) and `coverage_<level>_<mask>.nc` on the product grid — per cell, the `kept_thickness` (the height above) and the `uncaptured_thickness`, the in-layer water the kept column didn't reach: from the bottom of the kept column down to `min(bathy, layer bottom)`, floored at 0.

`contiguous_from_top` is the default prescription. `require_top` is a **thickness of the layer's own top** — the metres below `level.low` that must be present — and each level carries its own in `levels.py` (the top 300 m: every level is `300`; `--require-top` overrides it). A cell **survives** only where every constituent reaching into the layer's top `require_top` metres is defined at all times and members. Constituents are atomic (a whole LocalGP layer or nothing), so a `require_top` that lands partway into one requires that whole constituent. Selection is by the constituent's declared bounds; each constituent is a single already-integrated value per cell (present or NaN — no internal depth). With `require_top = 300`: `0_2000` requires `15_20` + `15_300`, whose bounds happen to tile exactly 0–300; `700_2000` requires `700_1850`, because `require_depth = 1000` falls within its 700–1850 bounds — so that one value must be present. The shallowest constituent's `n_fac` reaches the layer top, so any positive `require_top` requires it. Within a surviving cell, walk the constituents from the layer top down and **keep** them until the first undefined one, then discard it and everything below (set to NaN, so they vanish from the nan-aware integral). The kept run's `n_fac`-weighted thickness is the cell's height (a kept `1800_1850` adds 3·50 = 150 m), so the volume is the true tapering ocean.

`fully_wet_nan` is the earlier prescription (bathy-driven): each constituent is classified against the standard bathy as fully wet (floor ≥ `bottom`), intersecting, or dry; a cell drops where any fully-wet constituent is undefined, a constituent contributes where not dry and defined (else 0), and the height is the level's full nominal thickness everywhere in-footprint (a slab).

"Defined" is judged across every member and timestep together, so the footprint is identical for all realizations and the ensemble spread reflects real spread rather than footprint jitter.

### Quantities

`--quantities` selects deliverables from `temporal_transforms.REGISTRY`. `--time-window` (`YEAR0:YEAR1`) sets the anomaly baseline and the years the trends are fit over; omitted, it spans all years.

| `--quantities` name | dims | what it is |
|---|---|---|
| `ohca` | (year,) | monthly area-integrated anomaly (window baseline), annual-averaged |
| `ohu` | (year,) | month-to-month tendency of the integral, annual-averaged; NaN-seeded at t0 |
| `ohca_trend` | scalar | OLS slope of the annual integral over the window |
| `ohu_trend` | scalar | OLS slope of the annual tendency over the window |
| `map` | (time, lat, lon) | per-cell monthly anomaly (window baseline) |

The integral-based quantities are **extensive** — the per-area submission field integrated over the footprint (e.g. TJ from a TJ/m² field), with the trends and tendency carrying the matching per-year and per-month scaling; `map` stays in the submission's per-area unit. Turning these into per-area target densities (OHCA in J/m², OHU in W/m², and so on) is the downstream packaging step's job, done from the geometry and constants below.

### Output

One NetCDF per level, `derive_<tag>_<level>.nc`: each requested quantity plus its `_sd` companion (omitted under `--no-ensemble`), with header attrs `level`, `area_m2` and `volume_m3` (both from the mask step — the tapered footprint area and column volume), the physical constants `cp0`/`rho0` (carried from the submissions when present), and `provenance_tag` / `provenance_link`. The factory emits these extensive quantities and geometry; packaging derives the intensive per-area densities from them.

## Usage

### Environment

Described in `Dockerfile` to generate a containerized environment; make a similar env in anaconda on blanca when running on the cluster.

### Test

Tests live in `tests/` and run under pytest — in the containerized environment:

```
docker image build -t ohc_derive:test .
docker container run -v $(pwd):/app ohc_derive:test pytest
```

### Run

See `derive.slurm` for a real example of running this on blanca at CU. With the ensemble on (the default), each constituent's `OHCENS_` sibling **must** sit next to its `OHC_` file or the loader exits, and every quantity gets a collapsed `_sd`. `--no-ensemble` is the central-only path (mean field, no `_sd`); central values are identical either way.

#### run.py options

All configuration is on the command line — no env, no config file. The available quantities are `temporal_transforms.REGISTRY`; the mask prescriptions are `masks.REGISTRY`.

| option | default | effect |
|---|---|---|
| `SUBMISSION.nc …` (positional) | *(required)* | the constituent `OHC_` submissions for the level, one per native constituent; the `OHCENS_` member siblings are found automatically. |
| `--level` | *(required)* | the synthetic level to build (`levels.LEVELS`), e.g. `0_2000`. |
| `--bathy` | *(required)* | standard bathymetry NetCDF on the common grid. |
| `--quantities` | *(required)* | comma list from `ohca,ohu,ohca_trend,ohu_trend,map`. Unknown names error. |
| `--mask` | `contiguous_from_top` | cross-layer mask prescription (`masks.REGISTRY`): `contiguous_from_top` or `fully_wet_nan`. |
| `--require-top` | *(the level's own)* | metres of the layer's own top (from `level.low`) that must be defined for a cell to survive; overrides the level's `require_top` (in `levels.py`). Used by `contiguous_from_top`, ignored by `fully_wet_nan`. |
| `--time-window` | *(all years)* | `YEAR0:YEAR1` — the anomaly baseline and the trend-fit years. |
| `--no-ensemble` | off (ensemble **on**) | mean field only — skip the `_sd` companions and do not read the `OHCENS_` siblings. |
| `--tag` | *(required)* | provenance tag: the **run token** in the filename (`derive_<tag>_<level>.nc`) **and** the `provenance_tag` header attr. Whitespace-stripped, never lowercased — must match the provenance record char-for-char. |
| `--provenance-link` | *(none)* | URL/path to the provenance record; written to the `provenance_link` header attr. |
| `--out` | `.` | output directory. |

## Adding a quantity or a mask

A **quantity**: write a recipe `f(primitives, window) -> DataArray(realization, …)` over the helpers in [`temporal_transforms.py`](temporal_transforms.py) and register it in `temporal_transforms.REGISTRY`. A **mask prescription**: write `f(level, constituents, reference_bathy, require_top) -> (masked, footprint, height)` and register it in `masks.REGISTRY` — `footprint` (lat, lon bool) gives the area, `height` (lat, lon metres) gives the volume. In both cases the runner and the combine do the rest — no other file changes.
