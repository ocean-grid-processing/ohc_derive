#!/usr/bin/env python3
"""ohc_derive factory: build the combined-level analysis quantities for one synthetic level.

Consumes native-level ME4OH submissions (values and NaN on the common grid) plus a standard
bathymetry, and works entirely on the common grid. One invocation handles one synthetic level, so
levels parallelize across jobs. Six steps, in order:

  1. load        the constituents' submissions (mean field + members) and the standard bathy
  2. mask        apply the chosen cross-layer mask prescription over the constituents
  3. primitives  reduce each constituent to its map-level primitives (integral, gridded field)
  4. build       compose the primitives into the requested deliverables (ohca, ohu, trends, map)
  5. collapse    per constituent, collapse the members to a standard deviation; central = mean field
  6. combine     n_fac sum of values, worst-case n_fac sum of standard deviations -> one dataset

Realization axis: the mean field and the members ride together on a leading `realization` axis
(index 0 is the mean field, the rest are members). Steps 3-4 transform every realization the same way;
step 5 reads the central value off index 0 and the spread off the members. So an anomaly demean along
time hits every realization, and each member is referenced to its own window mean.

Members stay per constituent until step 5; step 6 sums values linearly and standard deviations
worst-case. Output is one dataset — each quantity plus its `_sd`, with the footprint area/volume and
cp0/rho0 as attrs; downstream packaging derives the per-area densities and applies names and layout.
"""
import argparse

import levels
import masks
import map_transforms
import temporal_transforms
import combine
import loader


def run(cfg):
    level = levels.get(cfg.level)

    # step 1 — load the constituents' submissions (mean + members) and the standard bathy.
    submissions = loader.load_submissions(cfg.submissions, with_members=not cfg.no_ensemble)
    reference_bathy = loader.load_bathy(cfg.bathy)

    blob = run_level(level, submissions, reference_bathy, cfg)
    loader.write_blob(blob, level, cfg)
    return blob


def run_level(level, submissions, reference_bathy, cfg):
    """The six steps for one synthetic level -> its dataset."""
    constituents = levels.constituents(level, submissions)          # the native levels this band needs

    # step 2 — apply the cross-layer mask; dumps the mask png and returns the footprint area.
    masked, area_m2 = masks.apply(cfg.mask, level, constituents, reference_bathy, out_dir=cfg.out)

    # step 3 — reduce each constituent to its map-level primitives (integral + gridded field).
    maps = map_transforms.apply(masked, level)

    # step 4 — compose the primitives into the requested deliverables (window sets baseline + trend fit).
    series = temporal_transforms.apply(cfg.quantities, maps, level, window=cfg.time_window)

    # step 5 — collapse each constituent's members to a standard deviation; central from the mean field.
    per_constituent = combine.collapse_sd(series)

    # step 6 — combine constituents: n_fac sum of values, worst-case n_fac sum of standard deviations.
    return combine.combine_synthetic(per_constituent, level, area_m2, _constants(submissions, level))


def _constants(submissions, level):
    """Physical constants (cp0, rho0) carried from the submissions, if present."""
    attrs = submissions[level.contributors[0].tag]["attrs"]
    return {k: float(attrs[k]) for k in ("cp0", "rho0") if k in attrs}


def main():
    ap = argparse.ArgumentParser(description="ohc_derive factory: ME4OH submissions -> one combined level")
    ap.add_argument("submissions", nargs="+", help="the constituent OHC_ submissions (+ OHCENS_ siblings)")
    ap.add_argument("--level", required=True, help="the synthetic level to build (e.g. 0_700)")
    ap.add_argument("--bathy", required=True, help="standard bathymetry (NetCDF on the common grid)")
    ap.add_argument("--quantities", required=True,
                    help="comma list of deliverables to build (see temporal_transforms.REGISTRY)")
    ap.add_argument("--mask", default="fully_wet_nan",
                    help="cross-layer mask prescription (see masks.REGISTRY)")
    ap.add_argument("--time-window", default=None, help="YEAR0:YEAR1 baseline/trend window (default: all years)")
    ap.add_argument("--no-ensemble", action="store_true", help="mean field only; no standard deviations")
    ap.add_argument("--tag", required=True, help="provenance tag (filename token + provenance_tag attr)")
    ap.add_argument("--provenance-link", default=None, help="URL/path to the provenance record")
    ap.add_argument("--out", default=".")
    cfg = ap.parse_args()
    cfg.quantities = [s.strip() for s in cfg.quantities.split(",") if s.strip()]
    if not cfg.quantities:
        raise SystemExit("nothing to build: give --quantities")
    cfg.time_window = _parse_window(cfg.time_window)
    run(cfg)


def _parse_window(s):
    """YEAR0:YEAR1 (or -) -> (int, int); None/empty -> None (all years)."""
    if not s:
        return None
    y0, y1 = (int(x) for x in s.replace("-", ":").split(":"))
    return (y0, y1)


if __name__ == "__main__":
    main()
