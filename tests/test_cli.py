"""End-to-end CLI: derive.main() over a synthetic submission."""
import glob
import sys

import pytest
import xarray as xr

import derive

ALL_VARS = [
    "ohc_timemean", "ohc_timemean_sd",
    "ohc_trend", "ohc_trend_sd",
    "ohc_integral", "ohc_integral_sd",
    "ohc_anom", "ohc_anom_sd",
    "ohc_anom12", "ohc_anom12_sd",
    "area_total",
]


def _run(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["derive.py"] + argv)
    derive.main()


def test_cli_all_transforms(write_pair, monkeypatch, tmp_path):
    sub, _ = write_pair()
    out = tmp_path / "out"
    out.mkdir()
    _run(monkeypatch, [sub, "--transforms", "all", "--out", str(out)])

    files = glob.glob(str(out / "derive_*.nc"))
    assert len(files) == 1
    ds = xr.open_dataset(files[0])
    for v in ALL_VARS:
        assert v in ds, v
    assert int(ds.attrs["ensemble"]) == 1            # int, not bool
    assert "transforms" in ds.attrs


def test_cli_no_ensemble(write_pair, monkeypatch, tmp_path):
    sub, _ = write_pair(write_sibling=False)          # no OHCENS_ needed
    out = tmp_path / "out"
    out.mkdir()
    _run(monkeypatch, [sub, "--transforms", "timemean,trend", "--no-ensemble", "--out", str(out)])

    ds = xr.open_dataset(glob.glob(str(out / "derive_*.nc"))[0])
    assert "ohc_timemean" in ds and "ohc_timemean_sd" not in ds
    assert "ohc_trend" in ds and "ohc_trend_sd" not in ds
    assert int(ds.attrs["ensemble"]) == 0


def test_cli_unknown_transform_exits(write_pair, monkeypatch, tmp_path):
    sub, _ = write_pair()
    with pytest.raises(SystemExit):
        _run(monkeypatch, [sub, "--transforms", "bogus", "--out", str(tmp_path)])


def test_cli_keep_members_integral(write_pair, monkeypatch, tmp_path):
    sub, _ = write_pair()
    out = tmp_path / "out"
    out.mkdir()
    _run(monkeypatch, [sub, "--transforms", "integral,area",
                       "--keep-members", "integral", "--out", str(out)])

    ds = xr.open_dataset(glob.glob(str(out / "derive_*.nc"))[0])
    assert "ohc_integral" in ds                       # central estimate
    assert "ohc_integral_ens" in ds                   # raw members (kept)
    assert "ohc_integral_sd" not in ds                # XOR — collapsed spread suppressed
    assert "member" in ds["ohc_integral_ens"].dims
    assert ds.attrs["members_kept"] == "integral"


def test_resolve_keep_members_valid():
    assert derive.resolve_keep_members("", ["integral", "area"], False) == set()
    assert derive.resolve_keep_members("integral", ["integral", "area"], False) == {"integral"}
    # 'all' = every ensemble transform being run (excludes the non-ensemble `area`)
    assert derive.resolve_keep_members("all", ["integral", "trend", "area"], False) == {"integral", "trend"}


@pytest.mark.parametrize("keep, names, no_ensemble", [
    ("integral", ["integral"], True),         # needs the ensemble
    ("area", ["area", "integral"], False),    # non-ensemble transform — no members to keep
    ("trend", ["integral", "area"], False),   # not selected by --transforms
    ("bogus", ["integral"], False),           # unknown name
])
def test_resolve_keep_members_hard_errors(keep, names, no_ensemble):
    with pytest.raises(SystemExit):
        derive.resolve_keep_members(keep, names, no_ensemble)
