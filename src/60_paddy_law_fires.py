"""Did Punjab's groundwater law move stubble burning into November? (step 60; links to south-asia-groundwater)

    python src/60_paddy_law_fires.py

Background. To slow the fall of the water table, the Punjab Preservation of Subsoil Water Act 2009 (and Haryana's act
of the same year) banned transplanting paddy before mid-June (15 June in 2009, later 20 June and in some years later),
so rice grows in the monsoon and draws less groundwater. A later crop means a later harvest, and a later harvest leaves
less time before wheat sowing: the stubble is burnt later, closer to November, when cooler, calmer air traps smoke over
the Indo-Gangetic Plain (Tripathi et al.; Singh et al. 2020, Sci. Rep.; Balwinder-Singh et al. 2019, Nature Sust.).

Test (a natural experiment): Pakistan's Punjab grows the same rice-wheat rotation in the same climate but had no such
law. If the law moved burning, the burning date in India's Punjab and Haryana should move later after 2009 *relative
to* Pakistan's Punjab (difference in differences); shared weather or satellite changes move both.

Data: MODIS Terra and Aqua active fires, daily 1 km (MOD14A1/MYD14A1 C6.1, fire mask 7-9), 2003-2025, 15 Sep-15 Dec,
counted in each region (FAO GAUL 2015 level 1 boundaries). Same sensors over the whole period.
Writes outputs/paddy_law_fires_daily.csv and outputs/paddy_law_fire_timing.csv.
"""
import sys
from pathlib import Path

import ee
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import smoglib as S  # noqa: E402

OUT = S.R / "outputs"
REGIONS = {"India: Punjab + Haryana": ("India", ["Punjab", "Haryana"]), "Pakistan: Punjab": ("Pakistan", ["Punjab"])}


def region(country, names):
    fc = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq("ADM0_NAME", country)).filter(ee.Filter.inList("ADM1_NAME", names))
    return fc.geometry()


def season(year, geoms):
    """Daily fire-pixel counts per region for one season, computed server-side."""
    start, end = ee.Date.fromYMD(year, 9, 15), ee.Date.fromYMD(year, 12, 16)
    def daily(coll):
        return ee.ImageCollection(coll).filterDate(start, end).select("FireMask")
    terra, aqua = daily("MODIS/061/MOD14A1"), daily("MODIS/061/MYD14A1")
    def count(img):
        f = img.gte(7).rename("fire")
        vals = {k: f.reduceRegion(ee.Reducer.sum(), g, 1000, maxPixels=1e9).get("fire") for k, g in geoms.items()}
        return ee.Feature(None, {"date": img.date().format("YYYY-MM-dd"), **vals})
    rows = []
    for sat, c in (("terra", terra), ("aqua", aqua)):
        for f in ee.FeatureCollection(c.map(count)).getInfo()["features"]:
            p = f["properties"]; rows += [{"date": p["date"], "sat": sat, "region": k, "fires": p.get(k) or 0} for k in geoms]
    return rows


def timing(d):
    """Per region and season: total fires and the dates by which 10, 50 and 90 % of the season's fires had burnt."""
    out = []
    for (r, y), g in d.groupby(["region", "year"]):
        g = g.groupby("date").fires.sum().sort_index(); c = g.cumsum() / g.sum()
        doy = lambda q: c[c >= q].index[0].dayofyear
        out.append({"region": r, "year": y, "fires": int(g.sum()), "d10": doy(.1), "d50": doy(.5), "d90": doy(.9),
                    "share_nov": g[g.index.month >= 11].sum() / g.sum()})
    return pd.DataFrame(out)


def did(t):
    """Difference in differences of the median burning date, 2003-2008 vs 2010-2025, with a bootstrap 95% interval."""
    w = t.pivot(index="year", columns="region", values="d50"); w["gap"] = w.iloc[:, 0] - w.iloc[:, 1]
    pre, post = w.loc[w.index <= 2008, "gap"], w.loc[w.index >= 2010, "gap"]
    est = post.mean() - pre.mean(); rng = np.random.default_rng(0)
    boot = [rng.choice(post, len(post)).mean() - rng.choice(pre, len(pre)).mean() for _ in range(5000)]
    return est, np.percentile(boot, [2.5, 97.5]), w


def main():
    S.init()
    f = OUT / "paddy_law_fires_daily.csv"
    d = pd.read_csv(f, parse_dates=["date"]) if f.exists() else pd.DataFrame()
    done = set(d.date.dt.year) if len(d) else set()
    geoms = {k: region(*v) for k, v in REGIONS.items()}
    for y in range(2003, 2026):
        if y not in done:
            d = pd.concat([d, pd.DataFrame(season(y, geoms)).assign(date=lambda x: pd.to_datetime(x.date))], ignore_index=True)
            d.to_csv(f, index=False); print("season", y, "done", flush=True)
    d["year"] = d.date.dt.year
    t = timing(d); t.round(3).to_csv(OUT / "paddy_law_fire_timing.csv", index=False)
    est, ci, w = did(t)
    print(w.round(1).to_string())
    print(f"\nShift in India's median burning date relative to Pakistan's, 2010-2025 vs 2003-2008: {est:+.1f} days (95% {ci[0]:+.1f} to {ci[1]:+.1f})")


if __name__ == "__main__":
    main()
