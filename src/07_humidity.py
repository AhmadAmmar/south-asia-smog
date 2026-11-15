"""Daily mean 2 m relative humidity (%) within 25 km of each city from ERA5 hourly temperature and dew point
(Magnus formula, over water), for the AOD to PM2.5 calibration: wet particles scatter more light per microgram,
so the same PM2.5 gives a higher AOD on humid days.

Writes outputs/city_humidity.csv (city, date, rh).
"""
import time

import ee
import pandas as pd

import smoglib as S

S.init()
pts = ee.FeatureCollection([ee.Feature(ee.Geometry.Point(xy).buffer(25000), {"city": c}) for c, xy in S.CITIES.items()])


def rh(i):
    t = i.select("temperature_2m").subtract(273.15)
    td = i.select("dewpoint_temperature_2m").subtract(273.15)
    e = td.multiply(17.625).divide(td.add(243.04)).exp()
    es = t.multiply(17.625).divide(t.add(243.04)).exp()
    return e.divide(es).multiply(100).rename("rh")


def day_rh(x):
    return ee.Image(ee.Algorithms.If(x.size(), x.map(rh).mean().toFloat(), ee.Image.constant(0).rename("rh").updateMask(0).toFloat()))


def month(y, m):
    start = ee.Date.fromYMD(y, m, 1)
    end = min(pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0), pd.Timestamp.today().normalize() - pd.Timedelta(days=1))
    n = end.day
    h = ee.ImageCollection("ECMWF/ERA5/HOURLY").filterDate(start, start.advance(1, "month"))
    img = ee.ImageCollection(ee.List.sequence(0, n - 1).map(
        lambda d: day_rh(h.filterDate(start.advance(d, "day"), start.advance(ee.Number(d).add(1), "day"))))).toBands()
    img = img.rename([f"d{d}" for d in range(n)])
    for k in range(8):
        try:
            feats = img.reduceRegions(pts, ee.Reducer.mean(), 27830).getInfo()["features"]
            break
        except Exception as e:
            if k == 7:
                raise
            time.sleep(30 * (k + 1))
    return [{"city": f["properties"]["city"], "date": f"{y}-{m:02d}-{d + 1:02d}", "rh": f["properties"].get(f"d{d}")}
            for f in feats for d in range(n)]


if __name__ == "__main__":
    f = S.OUT / "city_humidity.csv"
    old = pd.read_csv(f) if f.exists() else pd.DataFrame(columns=["city", "date", "rh"])
    have = set(old.date.str[:7])
    rows = []
    for y, m in S.months():
        if f"{y}-{m:02d}" in have and not S.fresh(y, m):
            continue
        rows += month(y, m)
    new = pd.DataFrame(rows)
    out = pd.concat([old[~old.date.str[:7].isin(set(new.date.str[:7]) if len(new) else set())], new])
    out.sort_values(["city", "date"]).to_csv(f, index=False)
    print(len(rows), "rows")
