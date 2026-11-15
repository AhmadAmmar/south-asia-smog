# South Asia smog from space

Seeing the smog season of South Asia from satellites: where it forms, when, how strongly, how it differs from year to
year, and what drives it (fires, emissions, a shallow winter boundary layer, weak wind). Every map and chart is made by
the code here from open data.

## Data

| Variable | Product | What it measures | Unit used |
|---|---|---|---|
| NO₂ | Sentinel-5P TROPOMI L3 (Earth Engine `COPERNICUS/S5P/OFFL/L3_NO2`) | Tropospheric column: traffic, power, industry | µmol m⁻² |
| CO | Sentinel-5P L3 CO | Total column: incomplete combustion, burning | mmol m⁻² |
| SO₂ | Sentinel-5P L3 SO2 | Column: coal, brick kilns, refineries | µmol m⁻² |
| HCHO | Sentinel-5P L3 HCHO | Tropospheric column: a marker of volatile organic compounds | µmol m⁻² |
| UV aerosol index | Sentinel-5P L3 AER_AI | Absorbing aerosol: smoke and dust | index |
| O₃ | Sentinel-5P L3 O3 | Total column (mostly stratospheric) | mmol m⁻² |
| AOD | MODIS MAIAC MCD19A2, 550 nm | Aerosol optical depth: all particles in the column | none |
| Fires | FIRMS (MODIS active fire, 1 km) | Fire pixels, confidence ≥ 50 | count |
| Weather | ERA5 hourly | Boundary layer height, wind, temperature, rain | SI |

Satellites see columns, not the air at nose height. A high NO₂ column over a city usually means high surface NO₂,
but particulate matter (PM2.5, the main driver of the air quality index) is only estimated from AOD through the
boundary layer height and humidity. The satellite smog index in this project is therefore labelled as an index of
satellite signals, never as an AQI.

## Steps

| Script | Does |
|---|---|
| `src/smoglib.py` | Region (60–98° E, 5–37° N), 0.1° grid, variables, cities |
| `src/01_monthly_grids.py` | Monthly mean and valid days per cell, 2019 onwards, for every variable and fire counts |
| `src/02_city_daily.py` | Daily values within 25 km of 12 cities, with ERA5 weather |
| `src/10_maps.py` | Smog from space, season against monsoon, monthly climatology, longitude–time, satellite smog index, trends |
| `src/20_city_charts.py` | Seasonal cycles, smog calendars, weather and fires against pollution |
| `src/03_fire_timing.py` | Daily Punjab fire detections by satellite overpass (Terra, Aqua; day, night) |
| `src/04_episode.py` | Daily NO₂, AOD, aerosol index and fires for one episode |
| `src/05_point_sources.py` | Power plants (WRI GPPD) and cities (Natural Earth) for attribution |
| `src/31_hotspots.py` | NO₂ and SO₂ hotspots, attribution to plants and cities, SO₂/NO₂ fingerprints, fire seasons |
| `src/32_city_analysis.py` | Weather on anomalies, AOD per km of mixing layer, fire-to-smog lag, fire timing |
| `src/40_episode_animation.py` | Day-by-day animation of an episode |

Figures and maps: `figures/` (PNG and PDF; the animation as GIF). Tables: `outputs/`.

Earth Engine code-editor version: `earth-engine-code/scripts/air-quality/south_asia_smog_monthly_grids.js`.
Decisions, problems met and their fixes: `docs/record.md`.

Run with the `eo` conda environment, signed in to Earth Engine.
