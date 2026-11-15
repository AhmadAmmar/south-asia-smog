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

## 2026-11-15: city daily series and charts

`outputs/city_daily.csv`: 34 332 city-days (12 cities, 2019-01 to 2026-10), no retries needed after the stacking fix.

**Smog-season ratios (Nov–Jan / Jul–Aug, `outputs/city_season_summary.csv`).** NO₂: Mumbai 4.9, Karachi 3.9,
Dhaka 3.8, Delhi 2.9, Lahore 2.5. AOD: Patna 2.3, Dhaka 2.2, Kolkata 2.1, Lucknow 1.5, Delhi 1.2, Lahore 0.7,
Islamabad 0.5, Peshawar 0.5. SO₂ and UV aerosol index ratios are meaningless (means near zero or negative) and are
not used.

**Annual cycles.** Delhi and Dhaka reach about 220 µmol m⁻² NO₂ in December–January, four times their August level.
Lahore's AOD peaks in July (1.3, dust on the few cloud-free monsoon days) with a second peak in early November (1.05);
Delhi's AOD peak is mid-November (1.3), the stubble-burning and Diwali weeks.

**Weather (Spearman rank correlation on smog-season days):**

| City | NO₂ – mixing height | NO₂ – wind | AOD – mixing height | AOD – wind | Median mixing height |
|---|---|---|---|---|---|
| Lahore | −0.56 | −0.32 | 0.15 | −0.42 | 201 m |
| Delhi | −0.59 | −0.53 | 0.05 | −0.45 | 260 m |
| Dhaka | −0.12 | −0.28 | 0.21 | 0.04 | 329 m |
| Patna | −0.36 | −0.28 | −0.04 | −0.23 | 327 m |

- NO₂ columns rise strongly as the mixing layer gets shallower in Lahore and Delhi; AOD does not. A shallow layer
  concentrates particles near the ground without changing the column total, so column AOD cannot show the
  surface effect; wind, which removes pollution, lowers both. Surface PM2.5 from AOD therefore needs AOD divided
  by mixing height, not AOD alone. Part of the NO₂–mixing height link may be the shorter NO₂ lifetime in winter
  (both peak in December); to separate, use anomalies from the daily climatology.
- The chart title earlier claimed "a shallow mixing layer traps aerosol"; the data do not show it in column AOD, so
  the title now states only what is plotted.

## 2026-11-15: hotspots and sources, fire timing, surface proxy, fire lag, episode

**Hotspots and sources** (`src/05_point_sources.py`, `src/31_hotspots.py`; `outputs/hotspots_*.csv`,
`fig_hotspots_no2`, `fig_hotspots_so2`, `fig_fingerprint`, `fig_fire_seasons`). Enhancement over a 2° running median of
the 2019–2026 mean; clusters above 4 robust standard deviations; attributed to the nearest thermal plant ≥ 300 MW
(WRI GPPD v1.3, 1 102 plants in the region) or city ≥ 300 000 (Natural Earth) within 30 km.
- NO₂, top 30: 19 coal plants, 5 gas/oil plants, 2 cities (Islamabad, Lahore), 4 unattributed. Top five: Rihand/
  Singrauli (+309 µmol m⁻²), Korba, Kamalanga (Talcher), Haripur (Dhaka), Ramagundam. Delhi's peak sits on Badarpur.
- SO₂, top 30: 17 coal plants (Rihand, Sterlite/Jharsuguda, Talcher, Neyveli, Koradi, Ramagundam, Chandrapur, Mundra).
  Unattributed but known: 36.4° N 60.8° E is the Khangiran (Shahid Hasheminejad) sour-gas refinery in Iran; 22.8° N
  71.0° E is the Morbi ceramic cluster in Gujarat. The largest SO₂ "hotspot", 15.0° N 88.8° E in the open Bay of Bengal,
  has no source and is treated as a retrieval artefact.
- Fingerprints: median SO₂/NO₂ enhancement ratio is 2.2 at coal plants against 0.4–0.6 at cities and gas plants, so the
  ratio separates coal from traffic and gas. Unattributed NO₂ hotspot 21 (24.65° N 84.15° E) has a coal-like ratio
  (3.4) and lies at Nabinagar, Bihar, where large coal units were commissioned after the inventory; hotspots 11 and 24
  (Chittorgarh and Kishangarh–Beawar, Rajasthan) have low ratios and match cement and stone clusters. These are leads,
  not confirmed attributions.
- CO and HCHO were dropped from the hotspot method: the 2° background fails at the Himalayan front, where the column
  falls with surface pressure, so their "hotspots" were terrain edges.
- Fires: Oct–Nov detections concentrate in Punjab and Haryana (rice residue), with smaller clusters in Madhya Pradesh;
  Mar–May fires are spread over central India and the north-east hills (wheat residue and forest burning).

**Fire timing** (`src/03_fire_timing.py`, MOD14A1/MYD14A1, Punjab both sides, 15 Sep–15 Dec; `fig_fire_timing`).

| Year | Terra ~10:30 | Aqua ~13:30 | Aqua / Terra | Night share |
|---|---|---|---|---|
| 2019 | 1 628 | 19 167 | 12 | 0.03 % |
| 2021 | 3 810 | 36 579 | 10 | 0.03 % |
| 2023 | 298 | 17 233 | 58 | 0.09 % |
| 2024 | 168 | 9 369 | 56 | 0.92 % |
| 2025 | 64 | 8 666 | 135 | 0.39 % |

Morning detections fell 98 % from 2021 to 2025, early-afternoon detections 76 %. Burning has moved later in the day.
Fires lit after about 14:00 are missed by both satellites, so the true fall in burning is smaller than either number;
how much smaller needs a geostationary sensor (e.g. INSAT-3D or Himawari-type hourly data).

**Weather on anomalies** (`src/32_city_analysis.py`, `outputs/weather_correlations.csv`, `fig_anomaly_weather`).
With the seasonal cycle removed, smog-season NO₂ still falls as mixing height rises (Delhi −0.49, Lahore −0.48,
Peshawar −0.51): the link is day-to-day meteorology, not only the shared winter cycle. AOD stays uncorrelated with
mixing height (−0.08 to 0.30) and falls with wind.

**Surface proxy** (AOD per km of mixing layer, not PM2.5; `fig_surface_proxy`). It tracks mixing height and wind
as surface pollution should (anomaly ρ with wind −0.52 Lahore, −0.55 Delhi). It peaks in the last days of December
in Lahore, Delhi and Peshawar and in mid-January in Dhaka and Kolkata, later than column AOD (mid-November).
Calibration to µg m⁻³ needs ground monitors (OpenAQ key pending) and humidity.

**Fire to smog lag** (`outputs/fire_lag.csv`, `fig_fire_lag`), 15 Oct–30 Nov 2019–2025. Correlation of Punjab fires
with Delhi AOD peaks two days later (ρ 0.32 all days, 0.42 on north-west wind days); Lahore the same (0.27, 0.37).
Both fires and AOD rise through the season, which inflates all lags; the peak at 2 days and the stronger link with
north-west wind are the transport signal.

**Episode** (`src/04_episode.py`, `src/40_episode_animation.py`; `figures/episode_2024-10-20_2024-11-30.gif`,
`fig_episode_peak`). The worst day on the plain was 11 November 2024 (plain-mean AOD 0.97): a continuous plume from the
Punjab fires along the plain to Patna. Over Lahore itself both MAIAC and TROPOMI are blank that day: the densest smog
and fog are flagged as cloud, so satellites miss the worst hours of the worst places.

## 2026-11-15: more episodes, source leads over time, CDS access

**Episodes, 20 Oct – 30 Nov of every year** (`figures/episode_<year>-10-20_<year>-11-30.gif`,
`fig_episode_peak_<year>.png`). Worst day on the plain (plain-mean AOD, 25–32° N, 73–88° E, days with ≥ 30 % valid
cells): 2019-11-27 (0.94), 2020-11-06 (0.67), 2021-11-06 (0.70), 2022-11-10 (0.91), 2023-11-20 (0.86),
2024-11-11 (0.97), 2025-11-01 (0.74). The worst day is not in the years with most fire detections (2020, 2021): the
plain-wide peak depends on stagnant weather as much as on fires.

**Source leads, yearly enhancement over the 2° background** (µmol m⁻²; 2026 is January–October only):

| Year | Nabinagar NO₂ | Nabinagar SO₂ | Chittorgarh NO₂ | Rihand NO₂ | Rihand SO₂ |
|---|---|---|---|---|---|
| 2019 | 11 | 48 | 31 | 258 | 750 |
| 2021 | 25 | 87 | 32 | 243 | 652 |
| 2023 | 31 | 118 | 45 | 255 | 668 |
| 2025 | 25 | 73 | 50 | 260 | 586 |
| 2026 | 25 | 56 | 46 | 245 | 430 |

- Nabinagar: NO₂ and SO₂ rose from 2019 to 2023, as units came into operation. This supports a coal plant missing
  from the 2019 inventory.
- Chittorgarh: NO₂ up by half with little SO₂, consistent with growing industry (cement) rather than coal power.
- Rihand: NO₂ flat but SO₂ down 43 % from 2019 to 2026, a sign of flue-gas desulphurisation coming into use at the
  Singrauli plants. To confirm against plant records before stating it.

**Copernicus CDS:** the key in `~/.cdsapirc` works and the ERA5 single-levels licence is accepted (test download on
2026-11-15). This project gets ERA5 through Earth Engine, so it does not depend on CDS.
