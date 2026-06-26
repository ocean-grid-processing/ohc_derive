#!/usr/bin/env python3
"""Derive per-product quantities from an ohc_ingest published submission.

    python derive.py SUBMISSION.nc [--transforms timemean,trend,integral,anomaly,area]
        [--no-ensemble] [--out DIR]

Input is the OHC_ submission .nc (TJ/m^2, mask already applied). Ensemble uncertainty (the _sd
companions) additionally reads the OHCENS_ sibling produced by `publish.py --ensemble`. Runs the
selected transforms, merges their outputs into one Dataset (variables of mixed rank sharing
coords), and writes one NetCDF per product/layer.

Requires: numpy, xarray>=2024.10, netCDF4.
"""
import argparse
import os
import sys

import xarray as xr

import loader
import transforms
from ensemble import with_uncertainty


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("submission", help="OHC_ submission .nc from ohc_ingest/publish.py")
    ap.add_argument("--transforms", default="all",
                    help="comma list of %s, or 'all'" % ",".join(transforms.REGISTRY))
    ap.add_argument("--no-ensemble", action="store_true",
                    help="central estimate only; skip the _sd companions (no OHCENS_ needed)")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()

    names = (list(transforms.REGISTRY) if args.transforms == "all"
             else [s.strip() for s in args.transforms.split(",")])
    unknown = [n for n in names if n not in transforms.REGISTRY]
    if unknown:
        sys.exit("unknown transform(s): %s; known: %s" % (unknown, list(transforms.REGISTRY)))

    product = loader.load_product(args.submission, with_ensemble=not args.no_ensemble)

    parts = []
    for name in names:
        fn, ensemble = transforms.REGISTRY[name]
        if ensemble and not args.no_ensemble:
            parts.append(with_uncertainty(fn, product))
        else:
            parts.append(fn(product["ohc"], product))
    result = xr.merge(parts)

    a = product.attrs
    result.attrs = {
        "Conventions": "CF-1.8",
        "source": a.get("source", ""),
        "product": a.get("product", ""),
        "experiment": a.get("experiment", ""),
        "period": a.get("period", ""),
        "layer_m": a.get("layer_m", ""),
        "cp0": a.get("cp0"), "rho0": a.get("rho0"),
        "mask_preset": a.get("mask_preset", ""),   # inherited from publish
        "transforms": ",".join(names),
        "ensemble": (not args.no_ensemble),
    }

    fname = "derive_%s_%s_lev%s.nc" % (a.get("product", "UNSET"),
                                       a.get("period", ""), a.get("layer_m", ""))
    path = os.path.join(args.out, fname)
    result.to_netcdf(path, engine="netcdf4")
    print("wrote", path)
    print("variables:", ", ".join(result.data_vars))


if __name__ == "__main__":
    main()
