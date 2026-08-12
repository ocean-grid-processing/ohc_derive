# ohc_derive output schema

One NetCDF per product/layer, `derive_<tag>_<period>_lev<low>_<high>.nc` (leading token = the
required `--tag`). It is a single
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
| `ohc_integral_anom` (+ `_sd`) | `(time,)` | TJ | `integral_anom` (OHCA — all-time mean removed) |
| `ohc_integral_tendency` (+ `_sd`) | `(time,)` | TJ | `integral_tendency` (OHU — month-to-month Δ, NaN at t0) |
| `ohc_anom` (+ `_sd`) | `(time, lat, lon)` | TJ/m² | `anomaly` (deseasonalized + detrended) |
| `ohc_anom12` (+ `_sd`) | `(month, lat, lon)` | TJ/m² | `anomaly` (seasonal cycle) |
| `area_total` | `()` | m² | `area` |

Every quantity is ensemble-propagated (carries a `_sd`) except `area_total`, which is pure grid
geometry with no uncertainty. `anomaly`'s `_sd` is correct but the heaviest to compute — its
per-member form is a full `(member, time, lat, lon)` stack (~7 GB transient, peak ~20 GB).

With the ensemble on, an ensemble transform yields a collapsed `<var>_sd`. Naming it in
`--keep-members` instead outputs the raw members `<var>_ens` (XOR with `_sd`) — the un-collapsed
per-member result. Use it when a consumer must reduce the ensemble itself *after* a later nonlinear
step: e.g. `ohc_gcos_emitter` takes the ensemble std of the **yearly** integral (yearly-mean per member,
then std across members), which the collapsed monthly `_sd` can't reproduce — so it asks for
`ohc_integral_ens` via `--keep-members integral`. Memory is the caller's call: keeping a gridded
transform's members (`anomaly` → `(member, time, lat, lon)`) can be large.

## Group attributes (provenance)

Inherited from the publish submission and carried through: `Conventions`, `source`, `experiment`,
`period`, `layer_m` (the `<low>_<high>` layer tag), `cp0`, `rho0`, `mask_preset`.
Added by the runner: `transforms` (which ran), `ensemble` (1/0 — whether the ensemble was read),
`members_kept` (comma list of transforms output as `<var>_ens` instead of `<var>_sd`, or `""`),
`provenance_tag` (the `--tag`, also the filename token) and, when given, `provenance_link` (URL/path
to the provenance record). `ohc_gcos_emitter` keys each mapped layer on `layer_m`.

## Parity with the original MATLAB

The opinionated definitions follow `ME4OH_Giglio_etal2026v2/` (`store_mean_trend_anom12_anom`
and its `helper_compute_*`), so results track the original:

- **`timemean`** = mean over time (`mean(DATA,3)`).
- **`trend`** = linear OLS slope fit to the **raw** field (season included), per second, on an
  **idealized uniform month axis** (`365.25/12` days), matching the helper's default time vector.
  The optional quadratic term in the MATLAB helper is not invoked there, so we fit linear only.
- **`anomaly`** = monthly climatology, `anom12 = climatology − overall mean`, deseason =
  `field − climatology[month]`, then a linear detrend of the deseasonalized field (the helper's
  `detrend`). Calendar-month binning equals the MATLAB position-mod-12 binning for the
  January-start records we use.

**Sanctioned deviation:** the original computes no ensemble spread on the gridded anomaly; we add
`*_sd` companions to every quantity except `area` (the symmetry decision). That's the only
intentional departure — everything else is meant to reproduce the MATLAB.

## Notes / forward-compat

- **`ohc_anom12` introduces a `month` coordinate** (1…12) alongside `time`; this is the one
  extra coordinate beyond the ingest grid.
- **`ohc_integral_tendency` (OHU)** is the backward first difference of the integral on the full
  `time` axis, NaN at `t0` (no prior month) — the prior-art convention, so it stays aligned
  month-for-month with the other series. It's the raw month-to-month change (matches the original's
  `data_tendency`); expressing it as a per-second uptake flux (W/m²) is a downstream units choice.
- **`ohc_integral_anom` (OHCA)** is the integral minus its whole-record mean — the canonical,
  parameter-free anomaly. A deliverable wanting a specific baseline *window* re-references it
  downstream (as the GCOS emitter does with 2005–2024).
- **Member-retained outputs** (keeping the full `(member, …)` stack for chaining a second
  nonlinear step) are large and belong in a separate file, not this summary Dataset.
