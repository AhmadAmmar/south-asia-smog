"""Monthly mean and number of valid days for every variable on the 0.1 degree South Asia grid, plus monthly fire counts.

    python src/01_monthly_grids.py [var ...]      default: all; resumes (skips months already saved)

Each month becomes data/grids/<var>/<YYYY-MM>.npz with arrays mean (in the unit of smoglib.VARS) and n (days with a
valid value). Daily images are first averaged per day so that a day with two overpasses counts once.
Fires: FIRMS (MODIS active fire, 1 km, Terra and Aqua) daily images; 'n' holds the number of 1 km fire pixels with
confidence >= 50 in each 0.1 degree cell over the month, 'mean' the mean brightness temperature (K).
The same logic for the Earth Engine code editor is in earth-engine/monthly_grids.js.
"""
import io
import sys
import time

import ee
import numpy as np

import smoglib as S

S.init()
GRID = S.grid()


def daily_mean(coll, band, scale, y, m):
    start = ee.Date.fromYMD(y, m, 1)
    end = start.advance(1, "month")
    c = ee.ImageCollection(coll).filterDate(start, end).select(band)
    ndays = end.difference(start, "day")
    days = ee.List.sequence(0, ndays.subtract(1))

    def per_day(d):
        d0 = start.advance(d, "day")
        day = c.filterDate(d0, d0.advance(1, "day"))
        # a day with no images gives an image with no bands; it is dropped by the filter below
        return ee.Image(ee.Algorithms.If(day.size(), day.mean().multiply(scale), ee.Image().select([]))).set("system:time_start", d0.millis())
    daily = ee.ImageCollection(days.map(per_day)).filter(ee.Filter.listContains("system:band_names", band))
    return daily.mean().rename("mean").addBands(daily.count().rename("n")).toFloat()


def fires(y, m):
    start = ee.Date.fromYMD(y, m, 1)
    c = ee.ImageCollection("FIRMS").filterDate(start, start.advance(1, "month"))
    hot = c.map(lambda i: i.select("T21").updateMask(i.select("confidence").gte(50)))
    proj = ee.Image(c.first()).select("T21").projection()
    count = hot.map(lambda i: i.mask().rename("n").toFloat()).sum().setDefaultProjection(proj)
    # sum of 1 km fire pixels within each 0.1 degree cell: reduce at native scale, then sum into the grid
    n = count.reduceResolution(ee.Reducer.sum().unweighted(), maxPixels=200).rename("n")
    return hot.mean().rename("mean").addBands(n).toFloat()


def fetch(img, tries=6):
    for k in range(tries):
        try:
            raw = ee.data.computePixels({"expression": img, "fileFormat": "NPY", "grid": GRID})
            return np.load(io.BytesIO(raw))
        except Exception as e:
            msg = str(e).lower()
            if "too large" in msg or "memory" in msg:
                raise
            if not any(w in msg for w in ("timeout", "deadline", "429", "500", "502", "503", "unavailable", "connection", "quota", "too many")):
                raise RuntimeError(f"not retried: {e}")
            time.sleep(10 * 2 ** k)
    raise RuntimeError("Earth Engine kept failing")


def save(var, y, m, a):
    out = S.DATA / "grids" / var
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / f"{y}-{m:02d}.npz", mean=a["mean"].astype("float32"), n=a["n"].astype("float32"))


def tiled(img):
    """Fetch in four horizontal strips when the whole region is too much for one request."""
    rows = []
    h = S.NY // 4
    for k in range(4):
        g = dict(GRID); g["dimensions"] = {"width": S.NX, "height": h if k < 3 else S.NY - 3 * h}
        at = dict(GRID["affineTransform"]); at["translateY"] = S.NORTH - k * h * S.RES; g["affineTransform"] = at
        for t in range(6):
            try:
                raw = ee.data.computePixels({"expression": img, "fileFormat": "NPY", "grid": g}); break
            except Exception:
                time.sleep(10 * 2 ** t)
        rows.append(np.load(io.BytesIO(raw)))
    return np.concatenate(rows)


if __name__ == "__main__":
    want = sys.argv[1:] or [*S.VARS, "fire"]
    for var in want:
        for y, m in S.months():
            if (S.DATA / "grids" / var / f"{y}-{m:02d}.npz").exists():
                continue
            img = fires(y, m) if var == "fire" else daily_mean(*S.VARS[var][:3], y, m)
            t0 = time.time()
            try:
                a = fetch(img)
            except RuntimeError:
                raise
            except Exception:
                a = tiled(img)
            save(var, y, m, a)
            print(f"{var} {y}-{m:02d} {time.time() - t0:5.1f}s valid cells {np.isfinite(a['mean']).mean():.2f}", flush=True)
