# Project record

## 2026-11-15: start

**Question.** Can the South Asian smog season be seen, measured and explained from satellite data alone, and which
signals (NO₂, aerosol, CO, fires, weather) lead and which follow?

**Decisions**
- Region 60–98° E, 5–37° N; grid 0.1° (about 11 km). TROPOMI's pixels are 5.5 × 3.5 km, so 0.1° keeps most detail
  while a month of the whole region is one 380 × 320 array.
- Period from January 2019: Sentinel-5P offline products are complete from then. Months to October 2026.
- Monthly means from daily means, so days with two overpasses do not count twice; the number of valid days is kept.
- Smog season = November to January; monsoon = July and August, for contrasts.
- Fire counts from FIRMS MODIS (1 km, confidence ≥ 50), summed into each 0.1° cell.
- Earth Engine quality filtering of Sentinel-5P L3 is accepted as is (qa thresholds in the catalogue).

**Problems and fixes**
- A request hung for 20 minutes with no time limit. Fix: `ee.data.setDeadline(180000)` in `smoglib.init`.
- May 2022: days without any Sentinel-5P image produced an image with no bands, which cannot be multiplied. The retry
  loop hid the error by retrying with growing waits. Fix: empty days produce an explicit empty image and are filtered;
  errors that retrying cannot cure are raised at once.
- Earth Engine project is in a restricted mode (one request at a time), so downloads run one after another.

**First look (NO₂, 40 months)**
- Smog-season NO₂ lies along the Indo-Gangetic Plain from Lahore to Dhaka, about twice its monsoon level.
- Over the Tibetan Plateau the monsoon NO₂ exceeds winter. To check: retrieval over snow and high terrain, and
  lightning NO₂ in summer, before reading it as real.

## 2026-11-15: all monthly grids (94 months × 8 layers) and the maps

**Problems and fixes**
- Cells with no valid day are written by Earth Engine as −inf, not NaN. Percentile colour limits became −inf and every
  map rendered as one colour. Fix: `load()` in `10_maps.py` turns non-finite means into NaN and their day count to 0.
- `02_city_daily.py` failed on "Too many concurrent aggregations" (HTTP 429, the restricted project). Fix: busy and
  time-out errors are retried with waits up to 10 minutes; other errors are raised at once.
- `fire 2026-10` and other months took up to 3.6 minutes per request; no failures.

**What the maps show** (box means, all months 2019-01 to 2026-10; smog = Nov–Jan, monsoon = Jul–Aug)

| Box | AOD smog / monsoon | NO₂ smog / monsoon (µmol m⁻²) | Month of highest AOD |
|---|---|---|---|
| Punjab, Lahore–Delhi (73–78° E, 28–32.5° N) | 0.58 / 0.75 | 49.6 / 32.5 | July |
| Middle Indo-Gangetic Plain, Lucknow–Patna | 0.95 / 0.61 | 40.0 / 26.9 | November |
| Bengal delta | 0.70 / 0.35 | 53.6 / 28.4 | January |
| Thar and Sindh | 0.44 / 0.91 | 24.1 / 23.0 | July |
| Singrauli coal belt (82.4–83° E, 24° N) | 0.68 / 0.50 | 227 / 93 | November |

- The winter aerosol maximum is an eastern and middle Indo-Gangetic Plain feature: AOD doubles from monsoon to winter
  over the Bengal delta and rises by half between Lucknow and Patna. In the west (Punjab, Sindh, Thar) column AOD peaks in
  July with desert dust, and the UV aerosol index (positive only over Thar and Balochistan) agrees. Column AOD therefore
  understates Lahore's winter smog, which sits in a shallow surface layer; the city series with boundary layer height
  are needed there. Monsoon AOD also has fewer clear days (valid share 76–83 % in July–August against 92–95 % in winter).
- NO₂ is higher in winter everywhere on the plain (×1.5 to ×1.9): a shallower mixing layer and a longer NO₂ lifetime
  in winter. The highest columns are coal power, not cities: Singrauli reaches 227 µmol m⁻² in winter. The
  longitude–time chart shows it as a dark vertical line at 83° E every year.
- Fire detections in Punjab (73–77.5° E, 29–32.5° N, October–November, pixel-days): 40 389 (2019), 84 470 (2020),
  106 165 (2021), 50 059 (2022), 39 701 (2023), 17 676 (2024), 12 320 (2025). An 88 % fall from 2021 to 2025. Part of
  the fall may be burning shifted to late afternoon, after the MODIS overpasses; geostationary or VIIRS night data would
  test this. It is reported as fewer detections, not yet as less burning.
- NO₂ smog-season trend (7 winters, Sen slope): +2 to +5 % per year over peninsular and central India; the large
  positive and negative patches over the Tibetan Plateau are retrieval noise over snow and low columns, not trends.
- The white patch in the south-west Arabian Sea is a MAIAC tile with no data, not clean air.
- The satellite smog index for November 2025 is highest over the middle plain and the coal belts of Chhattisgarh and
  Odisha; Delhi and Dhaka stand out among cities.
- The 429 errors were caused by the request itself: one reduceRegions per day meant 31 aggregations in one call.
  Fix: the days of a month are stacked as bands (`toBands`) and reduced once; a month now takes about 5 s.
  ERA5 2 m temperature is kept in kelvin.
