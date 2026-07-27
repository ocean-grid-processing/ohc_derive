# Test environment for ohc_derive — deps only, no code copied in (mount the source at runtime).
FROM python:3.12-slim

# numpy/xarray/netCDF4 are the runtime deps; pandas comes with xarray; pytest to run the suite.
RUN pip install --no-cache-dir numpy "xarray>=2024.10" netCDF4 pytest

WORKDIR /app

