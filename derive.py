#!/usr/bin/env python3
"""Derive per-product quantities from an ohc_ingest published submission.

    python derive.py SUBMISSION.nc --tag OP20260127b [--provenance-link URL]
        [--transforms timemean,trend,integral,anomaly,area]
        [--no-ensemble] [--keep-members integral] [--out DIR]

--tag is required: the filename run token (derive_<tag>_<period>_lev<layer>.nc) and the
provenance_tag header attr.

Input is the OHC_ submission .nc (TJ/m^2, mask already applied). With the ensemble on, each
ensemble transform yields a collapsed `<var>_sd` spread; naming it in `--keep-members` instead
outputs the raw members `<var>_ens` (XOR) — for a consumer that must reduce the ensemble itself
after a later nonlinear step. Either reads the OHCENS_ sibling produced by `publish.py --ensemble`.
Runs the selected transforms, merges their outputs into one Dataset (variables of mixed rank
sharing coords), and writes one NetCDF per product/layer.

Requires: numpy, xarray>=2024.10, netCDF4.
"""
import argparse
import os
import sys

import xarray as xr

import loader
import transforms
from ensemble import with_uncertainty, with_members


def resolve_keep_members(keep_arg, names, no_ensemble):
    """Parse/validate `--keep-members` into a set. Any misuse is a hard error (nothing silent).

    Rules: needs the ensemble; must be a subset of the selected transforms; ensemble transforms
    only (a non-ensemble transform has no members to keep). `all` = every ensemble transform run.
    """
    if not keep_arg:
        return set()
    if no_ensemble:
        sys.exit("--keep-members needs the ensemble; drop --no-ensemble")
    if keep_arg == "all":
        return {n for n in names if transforms.REGISTRY[n][1]}
    keep = {s.strip() for s in keep_arg.split(",")}
    unknown = [n for n in keep if n not in transforms.REGISTRY]
    if unknown:
        sys.exit("unknown transform(s) in --keep-members: %s" % unknown)
    not_run = [n for n in keep if n not in names]
    if not_run:
        sys.exit("--keep-members names transform(s) not selected by --transforms: %s" % not_run)
    non_ensemble = [n for n in keep if not transforms.REGISTRY[n][1]]
    if non_ensemble:
        sys.exit("--keep-members names non-ensemble transform(s) (no members to keep): %s" % non_ensemble)
    return keep


def _sanitize_tag(tag):
    """Strip all whitespace from a provenance tag; never lowercase or otherwise munge it — it must
    match the provenance record char-for-char."""
    return "".join(tag.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("submission", help="OHC_ submission .nc from ohc_ingest/publish.py")
    ap.add_argument("--transforms", default="all",
                    help="comma list of %s, or 'all'" % ",".join(transforms.REGISTRY))
    ap.add_argument("--no-ensemble", action="store_true",
                    help="central estimate only; skip the _sd companions (no OHCENS_ needed)")
    ap.add_argument("--keep-members", default="",
                    help="comma list of transforms (or 'all') to output as raw members (<var>_ens) "
                         "instead of the collapsed <var>_sd; ensemble transforms only")
    ap.add_argument("--tag", required=True,
                    help="provenance tag: the filename's run token (derive_<tag>_<period>_lev<layer>.nc) "
                         "AND the provenance_tag header attr.")
    ap.add_argument("--provenance-link", default=None,
                    help="URL/path to the provenance record; written to the provenance_link header attr")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    args.tag = _sanitize_tag(args.tag)

    names = (list(transforms.REGISTRY) if args.transforms == "all"
             else [s.strip() for s in args.transforms.split(",")])
    unknown = [n for n in names if n not in transforms.REGISTRY]
    if unknown:
        sys.exit("unknown transform(s): %s; known: %s" % (unknown, list(transforms.REGISTRY)))

    keep = resolve_keep_members(args.keep_members, names, args.no_ensemble)

    product = loader.load_product(args.submission, with_ensemble=not args.no_ensemble)

    parts = []
    for name in names:
        fn, ensemble = transforms.REGISTRY[name]
        if ensemble and not args.no_ensemble:
            # ensemble output is XOR: raw members (kept) or the collapsed spread (not kept)
            parts.append(with_members(fn, product) if name in keep
                         else with_uncertainty(fn, product))
        else:
            parts.append(fn(product["ohc"], product))
    result = xr.merge(parts)

    a = product.attrs
    result.attrs = {
        "Conventions": "CF-1.8",
        "source": a.get("source", ""),
        "experiment": a.get("experiment", ""),
        "period": a.get("period", ""),
        "layer_m": a.get("layer_m", ""),
        "cp0": a.get("cp0"), "rho0": a.get("rho0"),
        "mask_preset": a.get("mask_preset", ""),   # inherited from publish
        "transforms": ",".join(names),
        "ensemble": int(not args.no_ensemble),     # NetCDF attrs can't be bool; 1/0
        "members_kept": ",".join(sorted(keep)),    # transforms output as <var>_ens (else "")
        "provenance_tag": args.tag,                # run token; pointer to the provenance record
    }
    if args.provenance_link is not None:
        result.attrs["provenance_link"] = args.provenance_link

    fname = "derive_%s_%s_lev%s.nc" % (args.tag, a.get("period", ""), a.get("layer_m", ""))
    path = os.path.join(args.out, fname)
    result.to_netcdf(path, engine="netcdf4")
    print("wrote", path)
    print("variables:", ", ".join(result.data_vars))


if __name__ == "__main__":
    main()
