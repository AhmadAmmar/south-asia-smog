"""Shared settings for the South Asia smog project: region, grid, variables, cities.

Every variable is a column amount or index seen from space, not a surface concentration. The Sentinel-5P
(TROPOMI) Level 3 products in Earth Engine are already gridded and quality-filtered by the harpconvert step
(qa_value > 0.75 for NO2, HCHO, SO2; > 0.5 for CO, AER_AI); see each dataset's Earth Engine catalogue page.
"""
from datetime import date
from pathlib import Path

import ee

R = Path(__file__).resolve().parent.parent
DATA, OUT, FIG = R / "data", R / "outputs", R / "figures"
PROJECT = "ee-ahmadammargeo"

# South Asia, from Balochistan to Myanmar's border, Sri Lanka to the Himalaya
WEST, EAST, SOUTH, NORTH = 60.0, 98.0, 5.0, 37.0
RES = 0.1                                   # degrees, about 11 km: close to TROPOMI's native 5.5 x 3.5 km, cheap to store
NX, NY = round((EAST - WEST) / RES), round((NORTH - SOUTH) / RES)
TRANSFORM = [RES, 0, WEST, 0, -RES, NORTH]

# name: (collection, band, scale to the unit, unit, label)
VARS = {
    "no2": ("COPERNICUS/S5P/OFFL/L3_NO2", "tropospheric_NO2_column_number_density", 1e6, "µmol m⁻²", "Tropospheric NO₂"),
    "co": ("COPERNICUS/S5P/OFFL/L3_CO", "CO_column_number_density", 1e3, "mmol m⁻²", "Carbon monoxide column"),
    "so2": ("COPERNICUS/S5P/OFFL/L3_SO2", "SO2_column_number_density", 1e6, "µmol m⁻²", "SO₂ column"),
    "hcho": ("COPERNICUS/S5P/OFFL/L3_HCHO", "tropospheric_HCHO_column_number_density", 1e6, "µmol m⁻²", "Tropospheric formaldehyde"),
    "uvai": ("COPERNICUS/S5P/OFFL/L3_AER_AI", "absorbing_aerosol_index", 1.0, "index", "UV absorbing aerosol index"),
    "o3": ("COPERNICUS/S5P/OFFL/L3_O3", "O3_column_number_density", 1e3, "mmol m⁻²", "Total ozone column"),
    "aod": ("MODIS/061/MCD19A2_GRANULES", "Optical_Depth_055", 0.001, "", "Aerosol optical depth, 550 nm (MAIAC)"),
}

CITIES = {
    "Lahore": (74.34, 31.55), "Delhi": (77.21, 28.61), "Dhaka": (90.41, 23.81), "Kolkata": (88.36, 22.57),
    "Karachi": (67.01, 24.86), "Kathmandu": (85.32, 27.71), "Peshawar": (71.58, 34.01), "Lucknow": (80.95, 26.85),
    "Patna": (85.14, 25.59), "Mumbai": (72.88, 19.08), "Colombo": (79.86, 6.93), "Islamabad": (73.05, 33.69),
}


def fresh(y, m, months_back=2):
    """True for the current and the previous months_back months: data may still be arriving (Sentinel-5P offline
    products about a week, ERA5 in Earth Engine up to a few months), so these are downloaded again on every run."""
    t = date.today()
    return (t.year * 12 + t.month) - (y * 12 + m) <= months_back


def init():
    ee.Initialize(project=PROJECT)
    ee.data.setDeadline(180000)          # no request may hang for more than 3 minutes; callers retry


def grid():
    return {"dimensions": {"width": NX, "height": NY}, "affineTransform": dict(zip(
        ["scaleX", "shearX", "translateX", "shearY", "scaleY", "translateY"], TRANSFORM)), "crsCode": "EPSG:4326"}


def months(start=(2019, 1), end=None):
    """Months from start to the present month (series always run to today; the current month is partial)."""
    today = date.today()
    end = end or (today.year, today.month)
    y, m = start
    while (y, m) <= end:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
