"""Ensemble uncertainty propagation.

Central estimate comes from the posterior-mean field (matching the mapping's official best
estimate); the 1-sigma companion comes from the spread across the 100 conditional simulations.
Because each transform reduces over time and broadcasts over leading dims, applying it to the
ensemble yields a member-dimensioned result we just collapse. For a nonlinear transform this is
proper Monte-Carlo propagation; for a linear one the central and the ensemble mean agree.
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
