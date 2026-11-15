"""Daily values in a 25 km radius around each city, 2019 to 2026: satellite columns and indices plus weather.

    python src/02_city_daily.py          resumes per variable and month; writes outputs/city_daily.csv

Satellite: daily mean of every Sentinel-5P and MAIAC variable in smoglib.VARS within 25 km of the centre, with the
share of the circle that had a valid value that day (cover). Weather from ERA5 hourly (ECMWF/ERA5/HOURLY, days averaged):
boundary layer height (m), 10 m wind speed (m/s), 2 m temperature (deg C), total precipitation (mm), surface pressure.
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


def sat_month(var, year, month):
    coll, band, scale = S.VARS[var][:3]
    start = ee.Date.fromYMD(year, month, 1)
    days = ee.List.sequence(0, start.advance(1, "month").difference(start, "day").subtract(1))
    c = ee.ImageCollection(coll).filterDate(start, start.advance(1, "month")).select(band)

    def per_day(d):
        d0 = start.advance(d, "day")
        img = c.filterDate(d0, d0.advance(1, "day")).mean().multiply(scale)
        img = ee.Image(ee.Algorithms.If(img.bandNames().size(), img.rename("v"), ee.Image().rename("v").toFloat()))
        img = img.addBands(img.mask().rename("cover"))
        fc = img.reduceRegions(pts, ee.Reducer.mean(), 1113.2)
        return fc.map(lambda f: f.set("date", d0.format("YYYY-MM-dd")))
    return ee.FeatureCollection(days.map(per_day)).flatten()


def met_month(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    days = ee.List.sequence(0, start.advance(1, "month").difference(start, "day").subtract(1))
    h = ee.ImageCollection("ECMWF/ERA5/HOURLY").filterDate(start, start.advance(1, "month"))

    def per_day(d):
        d0 = start.advance(d, "day")
        x = h.filterDate(d0, d0.advance(1, "day"))
        m = x.select(["boundary_layer_height", "temperature_2m", "surface_pressure"]).mean()
        u, v = x.select("u_component_of_wind_10m").mean(), x.select("v_component_of_wind_10m").mean()
        ws = x.map(lambda i: i.select("u_component_of_wind_10m").hypot(i.select("v_component_of_wind_10m"))).mean().rename("wind")
        p = x.select("total_precipitation").sum().multiply(1000).rename("precip")
        img = m.addBands([ws, p, u.rename("u10"), v.rename("v10")])
        return img.reduceRegions(pts, ee.Reducer.mean(), 27830).map(lambda f: f.set("date", d0.format("YYYY-MM-dd")))
    return ee.FeatureCollection(days.map(per_day)).flatten()


def get(fc, cols):
    for k in range(6):
        try:
            rows = fc.getInfo()["features"]
            return pd.DataFrame([{c: r["properties"].get(c) for c in cols} for r in rows])
        except Exception as e:
            if k == 5:
                raise
            time.sleep(15 * 2 ** k)


if __name__ == "__main__":
    for year, month in S.months():
        for var in [*S.VARS, "met"]:
            f = PARTS / f"{var}_{year}-{month:02d}.csv"
            if f.exists():
                continue
            t0 = time.time()
            if var == "met":
                df = get(met_month(year, month), ["city", "date", "boundary_layer_height", "temperature_2m", "surface_pressure", "wind", "precip", "u10", "v10"])
            else:
                df = get(sat_month(var, year, month), ["city", "date", "v", "cover"]).rename(columns={"v": var, "cover": f"{var}_cover"})
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
