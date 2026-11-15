"""Daily values in a 25 km radius around each city, 2019 to 2026: satellite columns and indices plus weather.

    python src/02_city_daily.py          resumes per variable and month; writes outputs/city_daily.csv

Satellite: daily mean of every Sentinel-5P and MAIAC variable in smoglib.VARS within 25 km of the centre, with the
share of the circle that had a valid value that day (cover). Weather from ERA5 hourly (ECMWF/ERA5/HOURLY, days averaged):
boundary layer height (m), 10 m wind speed (m/s), 2 m temperature (K), total precipitation (mm), surface pressure.
Mixing height and wind decide how far pollution is diluted, which is why winter smog sits low over the plain.
"""
import time

import ee
import pandas as pd

import smoglib as S

S.init()
pts = ee.FeatureCollection([ee.Feature(ee.Geometry.Point(xy).buffer(25000), {"city": c}) for c, xy in S.CITIES.items()])
PARTS = S.OUT / "city_daily_parts"
PARTS.mkdir(parents=True, exist_ok=True)


def stacked(daily, ndays, scale_m, cols):
    """One reduceRegions over a month of daily images stacked as bands (d_col), instead of one per day: the restricted
    Earth Engine project allows a single aggregation at a time. Returns a feature collection with one row per city."""
    img = ee.ImageCollection(daily).toBands()
    names = [f"{d}_{c}" for d in range(ndays) for c in cols]
    return img.rename(names).reduceRegions(pts, ee.Reducer.mean(), scale_m)


def ndays(year, month):
    return (pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(0)).day


def sat_month(var, year, month):
    coll, band, scale = S.VARS[var][:3]
    start = ee.Date.fromYMD(year, month, 1)
    c = ee.ImageCollection(coll).filterDate(start, start.advance(1, "month")).select(band)

    def per_day(d):
        d0 = start.advance(d, "day")
        day = c.filterDate(d0, d0.advance(1, "day"))
        img = ee.Image(ee.Algorithms.If(day.size(), day.mean().multiply(scale), ee.Image.constant(0).updateMask(0))).rename("v").toFloat()
        return img.addBands(img.mask().rename("cover").toFloat())
    n = ndays(year, month)
    return stacked(ee.List.sequence(0, n - 1).map(per_day), n, 1113.2, ["v", "cover"]), ["v", "cover"]


MET = ["boundary_layer_height", "temperature_2m", "surface_pressure", "wind", "precip", "u10", "v10"]


def met_month(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    h = ee.ImageCollection("ECMWF/ERA5/HOURLY").filterDate(start, start.advance(1, "month"))

    def per_day(d):
        d0 = start.advance(d, "day")
        x = h.filterDate(d0, d0.advance(1, "day"))
        m = x.select(["boundary_layer_height", "temperature_2m", "surface_pressure"]).mean()
        u, v = x.select("u_component_of_wind_10m").mean(), x.select("v_component_of_wind_10m").mean()
        ws = x.map(lambda i: i.select("u_component_of_wind_10m").hypot(i.select("v_component_of_wind_10m"))).mean().rename("wind")
        p = x.select("total_precipitation").sum().multiply(1000).rename("precip")
        return m.addBands([ws, p, u.rename("u10"), v.rename("v10")]).toFloat()
    n = ndays(year, month)
    return stacked(ee.List.sequence(0, n - 1).map(per_day), n, 27830, MET), MET


def get(req, year, month):
    fc, cols = req
    for k in range(10):
        try:
            feats = fc.getInfo()["features"]
            break
        except Exception as e:
            busy = "concurrent" in str(e) or "429" in str(e)
            if k == 9 or not (busy or "timed out" in str(e).lower() or "deadline" in str(e).lower()):
                raise
            print(f"  retry {k + 1}: {str(e)[:80]}", flush=True)
            time.sleep(min(60 * (k + 1), 600) if busy else 15 * 2 ** k)
    rows = []
    for f in feats:
        p = f["properties"]
        for d in range(ndays(year, month)):
            rows.append({"city": p["city"], "date": f"{year}-{month:02d}-{d + 1:02d}", **{c: p.get(f"{d}_{c}") for c in cols}})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    for year, month in S.months():
        for var in [*S.VARS, "met"]:
            f = PARTS / f"{var}_{year}-{month:02d}.csv"
            if f.exists():
                continue
            t0 = time.time()
            if var == "met":
                df = get(met_month(year, month), year, month)
            else:
                df = get(sat_month(var, year, month), year, month).rename(columns={"v": var, "cover": f"{var}_cover"})
            df.to_csv(f, index=False)
            print(f"{var} {year}-{month:02d}: {len(df)} rows, {time.time() - t0:.0f}s", flush=True)
    parts = {}
    for f in sorted(PARTS.glob("*.csv")):
        var = f.stem.rsplit("_", 1)[0]
        parts.setdefault(var, []).append(pd.read_csv(f))
    out = None
    for var, dfs in parts.items():
        d = pd.concat(dfs)
        out = d if out is None else out.merge(d, on=["city", "date"], how="outer")
    out.sort_values(["city", "date"]).to_csv(S.OUT / "city_daily.csv", index=False)
    print("city_daily.csv", out.shape)
