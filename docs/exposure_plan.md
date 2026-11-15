# Who breathes what: population exposure to PM2.5 and NO2 in South Asia

Plan, 2026-11-15. Research analysis stays private until submitted; the public portal shows data products only.

## Question
How much PM2.5 and NO2 does each person in South Asia breathe, where, when, and who carries most of it, at
neighbourhood and street scale, daily to yesterday? Expressed as concentration, inhaled dose, cigarette
equivalent, and health burden, with uncertainty.

## Why it is a contribution
- Existing exposure numbers (GBD, AQLI, Berkeley Earth) are annual, about 1–10 km, end years before today, and
  stop at the district. Here: daily, 1 km for PM2.5 and 100 m for NO2 in cities, to yesterday.
- Exposure inequality inside cities (street proximity, informal settlements, slums, wealth) is almost unmeasured in
  South Asia.
- The cigarette figure (Berkeley Earth: 22 ug m-3 for 24 h about one cigarette, matched on mortality) is tested
  rather than repeated: compared with the inhaled dose and with GBD-style relative risk, with its assumptions shown.

## Steps
1. **Ground truth.** OpenAQ v3, every reference PM2.5 and NO2 monitor in 60–98 E, 5–37 N (CPCB, Pakistan EPAs,
   StateAir, Bangladesh DoE), daily, 2019 to yesterday. Low-cost sensors kept separately for a later test with
   humidity correction. (`src/08_openaq_region.py`)
2. **Daily 1 km PM2.5 model.** Machine learning (gradient boosting, then quantile forests for intervals) trained on
   monitor days; predictors: MAIAC AOD (with gap filling), Sentinel-5P NO2/CO/UVAI, ERA5 boundary-layer height,
   humidity, wind, temperature, FIRMS fire upwind, population, built-up, OSM road density, land cover, elevation, and
   a published annual surface (ACAG V6 GL) as prior. Spatial and temporal block validation, leave-one-city-out.
3. **Street-scale NO2 in cities.** Land-use regression at 100 m: Sentinel-5P as background, OSM major-road length
   within 50–1000 m, intersections, industry and brick kilns, power plants (WRI), built density.
4. **People.** WorldPop 100 m (age and sex), GHS-POP 2025, GHSL built-up and settlement model; Meta relative wealth
   index; geoBoundaries ADM2 districts; OSM slum and informal settlement tags where present.
5. **Exposure.** Population-weighted daily means by district and city; distribution of person-days above WHO 2021
   (15 PM2.5, 25 NO2 daily) and national standards; inhaled dose = concentration × ventilation (age-specific, EPA
   Exposure Factors) × indoor infiltration (sensitivity range); cigarette equivalent with its caveats.
6. **Burden.** GBD 2021 PM2.5 relative risks (or GEMM), baseline rates by country; deaths and life-years
   attributable, AQLI-style life expectancy loss; Monte Carlo over model, risk and population uncertainty.
7. **Inequality.** Concentration curves and Gini of exposure against wealth, distance to major roads and settlement
   type; which neighbourhoods breathe most per person.
8. **Portal.** Static site (GitHub Pages) with maps and city pages, daily refresh by a scheduled local job that
   reruns the incremental scripts and pushes the data products.
