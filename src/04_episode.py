"""Daily NO2, AOD and fire detections for one smog episode over the Indo-Gangetic Plain (66-92 E, 21-35 N, 0.1 deg),
for the animation in 40_episode_animation.py.

    python src/04_episode.py 2024-10-20 2024-11-30

One stacked request per variable (days as bands). Saves data/episode/<start>_<end>.npz with arrays (day, y, x).
"""
import sys
import time

import ee
import numpy as np
import pandas as pd

import smoglib as S

S.init()
W, E, SO, N = 66.0, 92.0, 21.0, 35.0
NX, NY = round((E - W) / S.RES), round((N - SO) / S.RES)
GRID = {"dimensions": {"width": NX, "height": NY}, "affineTransform": {"scaleX": S.RES, "shearX": 0, "translateX": W,
        "shearY": 0, "scaleY": -S.RES, "translateY": N}, "crsCode": "EPSG:4326"}


def daily(var, d0):
    """One day's image of a variable for the episode (fire: FIRMS detections at 50% confidence or more)."""
    if var == "fire":
        c = ee.ImageCollection("FIRMS").filterDate(d0, d0.advance(1, "day"))
        hot = c.map(lambda i: i.select("confidence").gte(50).selfMask().rename("v"))
        proj = ee.Image(ee.ImageCollection("FIRMS").first()).projection()
        n = hot.map(lambda i: i.unmask(0).toFloat()).sum().setDefaultProjection(proj)
        return ee.Image(ee.Algorithms.If(c.size(), n.reduceResolution(ee.Reducer.sum().unweighted(), maxPixels=200),
                                         ee.Image.constant(0))).rename("v").toFloat()
    coll, band, scale = S.VARS[var][:3]
    c = ee.ImageCollection(coll).filterDate(d0, d0.advance(1, "day")).select(band)
    return ee.Image(ee.Algorithms.If(c.size(), c.mean().multiply(scale), ee.Image.constant(0).updateMask(0))).rename("v").toFloat()


def stack(var, start, n):
    """Daily images of a variable over n days from start, stacked and fetched (up to eight attempts)."""
    s = ee.Date(start)
    img = ee.ImageCollection(ee.List.sequence(0, n - 1).map(lambda d: daily(var, s.advance(d, "day")))).toBands()
    for k in range(8):
        try:
            raw = ee.data.computePixels({"expression": img, "fileFormat": "NUMPY_NDARRAY", "grid": GRID})
            a = np.stack([raw[f].astype(float) for f in raw.dtype.names])
            a[~np.isfinite(a)] = np.nan
            return a
        except Exception as e:
            if k == 7:
                raise
            print("  retry", str(e)[:80], flush=True); time.sleep(30 * (k + 1))


if __name__ == "__main__":
    a, b = sys.argv[1:3] if len(sys.argv) > 2 else ("2024-10-20", "2024-11-30")
    days = pd.date_range(a, b)
    out = {}
    for v in ("no2", "aod", "uvai", "fire"):
        t = time.time(); out[v] = stack(v, a, len(days)); print(v, out[v].shape, f"{time.time() - t:.0f}s", flush=True)
    d = S.DATA / "episode"; d.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / f"{a}_{b}.npz", dates=np.array([str(x.date()) for x in days]),
                        extent=np.array([W, E, SO, N]), **out)
