"""The synthetic-level plan: the combined-level table.

A synthetic level is a weighted sum of native ME4OH levels ("constituents"), shallowest first. `n_fac`
scales a thin measured layer up to the slab it stands in for; `top`/`bottom` are the constituent's own
dbar bounds, used against the standard bathy for the fully-wet / seafloor / dry test in step 2.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Contributor:
    tag: str        # native-level tag "top_bottom", matches the submission's mapped_layer attr
    n_fac: int      # thin-layer multiplier
    top: int        # dbar, shallow edge
    bottom: int     # dbar, deep edge


@dataclass(frozen=True)
class Level:
    name: str
    contributors: tuple

    @property
    def low(self):
        return int(self.name.split("_")[0])

    @property
    def high(self):
        return int(self.name.split("_")[1])

    @property
    def nominal_thickness(self):
        """Nominal layer thickness in metres: n_fac-weighted sum of the constituent thicknesses."""
        return sum(c.n_fac * (c.bottom - c.top) for c in self.contributors)


LEVELS = [
    Level("0_300",  (Contributor("15_20", 3, 15, 20), Contributor("15_300", 1, 15, 300))),
    Level("0_700",  (Contributor("15_20", 3, 15, 20), Contributor("15_300", 1, 15, 300),
                     Contributor("300_700", 1, 300, 700))),
    Level("0_1000", (Contributor("15_20", 3, 15, 20), Contributor("15_300", 1, 15, 300),
                     Contributor("300_700", 1, 300, 700), Contributor("700_1000", 1, 700, 1000))),
    Level("700_2000", (Contributor("700_1850", 1, 700, 1850), Contributor("1800_1850", 3, 1800, 1850))),
    Level("0_2000", (Contributor("15_20", 3, 15, 20), Contributor("15_300", 1, 15, 300),
                     Contributor("300_700", 1, 300, 700), Contributor("700_1850", 1, 700, 1850),
                     Contributor("1800_1850", 3, 1800, 1850))),
]

_BY_NAME = {lv.name: lv for lv in LEVELS}


def get(name):
    """The Level for `name`."""
    if name not in _BY_NAME:
        raise SystemExit("unknown synthetic level %r; known: %s" % (name, list(_BY_NAME)))
    return _BY_NAME[name]


def constituents(level, submissions):
    """Attach each contributor's loaded submission to its plan entry, shallowest first.

    Returns a list of dicts {tag, n_fac, top, bottom, field_value}, where `field_value` is the
    (realization, time, lat, lon) stack for that native level. Errors if a needed submission wasn't
    provided.
    """
    out = []
    for c in level.contributors:
        if c.tag not in submissions:
            raise SystemExit("level %s needs native layer %s, which wasn't among the submissions"
                             % (level.name, c.tag))
        out.append({"tag": c.tag, "n_fac": c.n_fac, "top": c.top, "bottom": c.bottom,
                    "field_value": submissions[c.tag]["field_value"]})
    return out
