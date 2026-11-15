"""Daily fire detections over Punjab (both sides of the border, 73-77.5 E, 29-32.5 N), 15 Sep to 15 Dec, 2019 to the present season,
split by satellite and overpass: Terra (about 10:30 and 22:30 local) and Aqua (about 13:30 and 01:30).

If farmers moved burning to late afternoon, after the Aqua overpass, the daytime detections fall while the share
seen at night (fires still smouldering at 22:30 and 01:30) should rise. MOD14A1/MYD14A1 collection 6.1: FireMask
7-9 = fire (low, nominal, high confidence); QA bit 2 = day (1) or night (0).

Writes outputs/punjab_fires_daily.csv (date, terra_day, terra_night, aqua_day, aqua_night: fire pixels, 1 km).
"""
import time

import ee
import pandas as pd

import smoglib as S

S.init()
BOX = ee.Geometry.Rectangle([73, 29, 77.5, 32.5], None, False)
COLS = ["terra_day", "terra_night", "aqua_day", "aqua_night"]


def day_image(d0):
    out = []
    for coll in ("MODIS/061/MOD14A1", "MODIS/061/MYD14A1"):
        c = ee.ImageCollection(coll).filterDate(d0, d0.advance(1, "day"))
        img = ee.Image(ee.Algorithms.If(c.size(), c.first(), ee.Image.constant([0, 0]).rename(["FireMask", "QA"]).toInt()))
        fire = img.select("FireMask").gte(7)
        day = img.select("QA").bitwiseAnd(4).neq(0)
        out += [fire.And(day), fire.And(day.Not())]
    return ee.Image.cat(out).rename(COLS).toFloat()


def season(year):
    start = ee.Date.fromYMD(year, 9, 15)
    n = 92
    stack = ee.ImageCollection(ee.List.sequence(0, n - 1).map(lambda d: day_image(start.advance(d, "day")))).toBands()
    stack = stack.rename([f"{d}_{c}" for d in range(n) for c in COLS])
    for k in range(8):
        try:
            p = stack.reduceRegion(ee.Reducer.sum(), BOX, 1000, maxPixels=1e9).getInfo()
            break
        except Exception as e:
            if k == 7:
                raise
            print("  retry", str(e)[:80], flush=True); time.sleep(30 * (k + 1))
    dates = pd.date_range(f"{year}-09-15", periods=n)
    return pd.DataFrame([{"date": dates[d].date(), **{c: p.get(f"{d}_{c}") for c in COLS}} for d in range(n)])


if __name__ == "__main__":
    frames = []
    for y in range(2019, pd.Timestamp.today().year + 1):   # the current season is partial up to today
        t = time.time(); frames.append(season(y)); print(y, f"{time.time() - t:.0f}s", flush=True)
    out = pd.concat(frames)
    out = out[pd.to_datetime(out.date) < pd.Timestamp.today().normalize()]       # no rows for days not yet observed
    out.to_csv(S.OUT / "punjab_fires_daily.csv", index=False)
