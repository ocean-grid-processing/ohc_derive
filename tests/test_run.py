"""run: window parsing, constant extraction, and an end-to-end run_level with a known OHCA."""
import types

import numpy as np
import xarray as xr

import run
import levels
import grid
import loader
import conftest


def test_window_token_uses_window_or_record_span():
    blob = xr.Dataset({"ohca": ("year", [1.0, 2.0])}, coords={"year": [2004, 2025]})
    assert loader._window_token(types.SimpleNamespace(time_window=(2005, 2024)), blob) == "2005_2024"
    assert loader._window_token(types.SimpleNamespace(time_window=None), blob) == "2004_2025"


def test_parse_window():
    assert run._parse_window("2005:2024") == (2005, 2024)
    assert run._parse_window("2005-2024") == (2005, 2024)
    assert run._parse_window(None) is None
    assert run._parse_window("") is None


def test_constants_extracts_present_only():
    subs = {"15_20": {"attrs": {"cp0": 3989.0, "rho0": 1030.0}}}
    assert run._constants(subs, levels.get("0_300")) == {"cp0": 3989.0, "rho0": 1030.0}


def test_constants_omits_missing():
    subs = {"15_20": {"attrs": {"cp0": 3989.0}}}
    assert run._constants(subs, levels.get("0_300")) == {"cp0": 3989.0}


def _ramped(slope, n_time=24):
    """A field uniform in space, equal to slope * month_index in time -> (1, time, lat, lon)."""
    t = slope * np.arange(float(n_time))
    arr = t[None, :, None, None] * np.ones((1, n_time, conftest.NLAT, conftest.NLON))
    return conftest.field(arr, conftest.months(n_time, start_year=2001))


def test_run_level_ohca_matches_hand_computed(tmp_path):
    # 15_20 = t, 15_300 = 2t (uniform in space) over 24 months (2001-2002); deep bathy -> all fully wet.
    # per-cell integral_i(t) = value_i * A; anomaly removes the whole-record mean (month 11.5);
    # annual means over each year give ohca_15_20 = [-6A, 6A], ohca_15_300 = [-12A, 12A];
    # n_fac combine (3, 1) -> [-30A, 30A].
    subs = {
        "15_20": {"field_value": _ramped(1.0), "attrs": {"cp0": 3989.0, "rho0": 1030.0}},
        "15_300": {"field_value": _ramped(2.0), "attrs": {"cp0": 3989.0, "rho0": 1030.0}},
    }
    reference_bathy = conftest.bathy([[1000.0, 1000.0, 1000.0], [1000.0, 1000.0, 1000.0]])
    cfg = types.SimpleNamespace(mask="fully_wet_nan", quantities=["ohca"], time_window=None,
                                require_top=None, tag="dev", out=str(tmp_path))

    blob = run.run_level(levels.get("0_300"), subs, reference_bathy, cfg)

    A = float(grid.cell_area(conftest.LAT, conftest.LON).sum())
    assert np.allclose(blob["ohca"].values, [-30.0 * A, 30.0 * A])
    assert "ohca_sd" not in blob.data_vars                          # mean-only run
    assert np.isclose(blob.attrs["area_m2"], A)
    assert np.isclose(blob.attrs["volume_m3"], A * 300)            # nominal thickness of 0_300


def test_run_level_with_members_produces_sd_and_geometry(tmp_path):
    subs = {
        "15_20": {"field_value": conftest.const_field(1.0, n_real=4, n_time=12),
                  "attrs": {"cp0": 3989.0, "rho0": 1030.0}},
        "15_300": {"field_value": conftest.const_field(10.0, n_real=4, n_time=12),
                   "attrs": {"cp0": 3989.0, "rho0": 1030.0}},
    }
    reference_bathy = conftest.bathy([[1000.0, 1000.0, 1000.0], [1000.0, 1000.0, 1000.0]])
    cfg = types.SimpleNamespace(mask="fully_wet_nan", quantities=["ohca"], time_window=None,
                                require_top=None, tag="dev", out=str(tmp_path))
    blob = run.run_level(levels.get("0_300"), subs, reference_bathy, cfg)
    A = float(grid.cell_area(conftest.LAT, conftest.LON).sum())
    assert "ohca" in blob.data_vars and "ohca_sd" in blob.data_vars
    assert np.allclose(blob["ohca"].values, 0.0, atol=1e-6 * A)     # constant field -> anomaly ~ 0 (machine precision)
    assert np.allclose(blob["ohca_sd"].values, 0.0)                # identical members -> zero spread
