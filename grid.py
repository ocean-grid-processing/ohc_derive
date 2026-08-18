"""Grid geometry for the common lat/lon grid."""
import numpy as np
import xarray as xr

EARTH_RADIUS_M = 6_371_000.0


def cell_area(lat, lon):
    """Spherical cell area (m^2) on a regular lat/lon grid -> DataArray(lat, lon)."""
    lat = np.asarray(lat, dtype="float64")
    lon = np.asarray(lon, dtype="float64")
    dlat = abs(lat[1] - lat[0])
    dlon = abs(lon[1] - lon[0])
    band = EARTH_RADIUS_M ** 2 * np.deg2rad(dlon) * (
        np.sin(np.deg2rad(lat + dlat / 2)) - np.sin(np.deg2rad(lat - dlat / 2)))
    return xr.DataArray(np.repeat(band[:, None], len(lon), axis=1),
                        dims=("lat", "lon"), coords={"lat": lat, "lon": lon})
