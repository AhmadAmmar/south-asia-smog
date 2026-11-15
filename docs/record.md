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
