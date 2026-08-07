"""The ensemble wrapper: central from the mean field, _sd from member spread."""
import numpy as np
import pytest

import transforms
from ensemble import with_members, with_uncertainty


def test_central_from_mean_field_and_sd(build_product):
    base = np.full((6, 2, 2), 4.0)
    offsets = np.array([-1.0, 0.0, 1.0])            # 3 members, constant offsets
    ens = np.stack([base + o for o in offsets], axis=0)
    p = build_product(base, ohc_ens=ens)

    out = with_uncertainty(transforms.time_mean, p)
    # central comes from the mean field (= base), not the ensemble mean
    assert np.allclose(out["ohc_timemean"].values, 4.0)
    # sd = std across members of the per-member time-mean = std(offsets, ddof=1)
    assert np.allclose(out["ohc_timemean_sd"].values, np.std(offsets, ddof=1))


def test_sd_companion_naming(build_product):
    base = np.ones((4, 2, 2))
    ens = np.stack([base, base * 1.1, base * 0.9], axis=0)
    p = build_product(base, ohc_ens=ens)
    out = with_uncertainty(transforms.trend, p)
    assert {"ohc_trend", "ohc_trend_sd"} <= set(out.data_vars)


# ddof=1 over a single member is DoF<=0 by design — NumPy's RuntimeWarning is expected here.
@pytest.mark.filterwarnings("ignore:Degrees of freedom <= 0 for slice:RuntimeWarning")
def test_single_member_sd_is_nan(build_product):
    base = np.ones((4, 2, 2))
    ens = base[None, ...]                            # one member -> ddof=1 undefined
    p = build_product(base, ohc_ens=ens)
    out = with_uncertainty(transforms.time_mean, p)
    assert np.all(np.isnan(out["ohc_timemean_sd"].values))


def test_with_members_keeps_members_and_central_no_sd(build_product):
    # with_members: central <var> from the mean field + raw members <var>_ens, and NO _sd (XOR).
    base = np.full((3, 2, 2), 2.0)                   # mean field (value 2), 3 timesteps
    ens = np.stack([base * 1.0, base * 2.0, base * 3.0], axis=0)   # members × value 2, 4, 6
    p = build_product(base, ohc_ens=ens)

    out = with_members(transforms.integral, p)
    assert "ohc_integral" in out.data_vars           # central, from the mean field
    assert "ohc_integral_sd" not in out.data_vars    # XOR — no collapsed spread
    assert out["ohc_integral_ens"].dims == ("member", "time")
    ca = float(p["cell_area"].sum())                 # integral = value · Σ cell_area
    assert np.allclose(out["ohc_integral"].values, 2.0 * ca)                # central (mean, value 2)
    assert np.allclose(out["ohc_integral_ens"].isel(member=0).values, 2.0 * ca)
    assert np.allclose(out["ohc_integral_ens"].isel(member=2).values, 6.0 * ca)
