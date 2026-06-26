# ohc_derive output schema

One NetCDF per product/layer, `derive_<product>_<period>_lev<low>_<high>.nc`. It is a single
`xr.Dataset` whose variables use different subsets of the shared coordinates
`(time, lat, lon, month, member)`. Results are variables (scalars too, as 0-d variables);
attributes carry only provenance.

## Conventions

- **One Dataset, mixed ranks.** A map is `(lat, lon)`, a series is `(time,)`, a cube is
  `(time, lat, lon)`, a climatology is `(month, lat, lon)`, a scalar is 0-d. They coexist.
- **Uncertainty companions.** An ensemble-propagated quantity `X` is paired with `X_sd`
  (identical shape) — the 1-sigma spread across the 100 conditional simulations. The central
  `X` is computed from the posterior-mean field; `X_sd` from the ensemble.
- **Scalars are 0-d variables**, not attributes (so they keep units and stay first-class for
  downstream comparison).
- **Masking.** The mask was applied upstream by publish (its preset is recorded in the source
  attrs); cells outside it are NaN. ohc_derive does not re-mask.

## Variables (current transforms)

| variable | dims | units | from transform |
|---|---|---|---|
| `ohc_timemean` (+ `_sd`) | `(lat, lon)` | TJ/m² | `timemean` |
| `ohc_trend` (+ `_sd`) | `(lat, lon)` | TJ/m²/s | `trend` |
| `ohc_integral` (+ `_sd`) | `(time,)` | TJ | `integral` |
| `ohc_anom` (+ `_sd`) | `(time, lat, lon)` | TJ/m² | `anomaly` (deseasonalized + detrended) |
| `ohc_anom12` (+ `_sd`) | `(month, lat, lon)` | TJ/m² | `anomaly` (seasonal cycle) |
| `area_total` | `()` | m² | `area` |

Every quantity is ensemble-propagated (carries a `_sd`) except `area_total`, which is pure grid
geometry with no uncertainty. `anomaly`'s `_sd` is correct but the heaviest to compute — its
per-member form is a full `(member, time, lat, lon)` stack (~7 GB transient, peak ~20 GB).

## Group attributes (provenance)

`Conventions`, `source`, `mapped_fields_tag`, `layer_top`, `layer_bottom`, `cp0`, `rho0`,
`mask_preset`, `transforms` (which ran), `ensemble` (whether `_sd` companions were produced).

## Notes / forward-compat

- **`ohc_anom12` introduces a `month` coordinate** (1…12) alongside `time`; this is the one
  extra coordinate beyond the ingest grid.
- **Ocean heat uptake (OHU)** would be `diff(OHC)/dt`, one timestep shorter, so when added it
  needs its own time coordinate (e.g. `time_ohu`) rather than reusing `time`.
- **Member-retained outputs** (keeping the full `(member, …)` stack for chaining a second
  nonlinear step) are large and belong in a separate file, not this summary Dataset.
