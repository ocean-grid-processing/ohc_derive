"""Ensemble uncertainty propagation.

Central estimate comes from the posterior-mean field (matching the mapping's official best
estimate); the 1-sigma companion comes from the spread across the 100 conditional simulations.
Because each transform addresses the field by dimension name, applying it to the ensemble carries
the leading `member` axis through untouched, giving a member-dimensioned result we then collapse.
For a nonlinear transform this is proper Monte-Carlo propagation; for a linear one the central and
the ensemble mean agree.
"""
import xarray as xr


def with_uncertainty(fn, product):
    """Run `fn` on the mean field (central) and on the ensemble (-> _sd companions)."""
    est = fn(product["ohc"], product)
    per_member = fn(product["ohc_ens"], product)
    sd = per_member.std("member", ddof=1)
    sd = sd.rename({v: v + "_sd" for v in list(sd.data_vars)})
    for v in sd.data_vars:
        sd[v].attrs = {"long_name": "ensemble 1-sigma of " + v[:-3]}
    return xr.merge([est, sd])


def _per_member(fn, product):
    """`fn` on the ensemble, keeping the `member` axis, renamed `<var>_ens`."""
    pm = fn(product["ohc_ens"], product)
    pm = pm.rename({v: v + "_ens" for v in list(pm.data_vars)})
    for v in pm.data_vars:
        pm[v].attrs = {"long_name": "per-member (conditional-simulation) " + v[:-4]}
    return pm


def with_members(fn, product):
    """Run `fn` on the mean field (central) and keep the ensemble raw (-> `_ens` companions).

    The symmetric counterpart of `with_uncertainty`: same central estimate, but the ensemble is
    kept as members instead of collapsed to a spread. Used when a downstream consumer must apply a
    nonlinear reduction to the ensemble *after* derive's boundary (e.g. the spread of a yearly
    mean), which the collapsed `_sd` can't provide.
    """
    est = fn(product["ohc"], product)
    return xr.merge([est, _per_member(fn, product)])
