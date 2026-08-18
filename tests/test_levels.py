"""levels: bounds, nominal thickness, lookup, and constituent assembly."""
import pytest

import levels
import conftest


def test_low_high():
    lv = levels.get("0_700")
    assert (lv.low, lv.high) == (0, 700)


@pytest.mark.parametrize("name, thickness", [
    ("0_300", 300),        # 3*(20-15) + 1*(300-15) = 15 + 285
    ("0_700", 700),        # + 1*(700-300) = 400
    ("0_2000", 2000),
    ("700_2000", 1300),    # 1*(1850-700) + 3*(1850-1800) = 1150 + 150
])
def test_nominal_thickness(name, thickness):
    assert levels.get(name).nominal_thickness == thickness


def test_get_unknown_exits():
    with pytest.raises(SystemExit):
        levels.get("3_4")


def test_constituents_shallowest_first_and_attached():
    lv = levels.get("0_700")
    subs = {c.tag: {"field_value": conftest.const_field(1.0), "attrs": {}} for c in lv.contributors}
    got = levels.constituents(lv, subs)
    assert [c["tag"] for c in got] == ["15_20", "15_300", "300_700"]
    assert [c["n_fac"] for c in got] == [3, 1, 1]
    assert (got[0]["top"], got[0]["bottom"]) == (15, 20)
    assert got[0]["field_value"] is subs["15_20"]["field_value"]


def test_constituents_missing_submission_exits():
    lv = levels.get("0_700")
    subs = {"15_20": {"field_value": conftest.const_field(1.0), "attrs": {}}}   # missing 15_300, 300_700
    with pytest.raises(SystemExit):
        levels.constituents(lv, subs)
