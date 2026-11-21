"""Does a Punjab fire darken Delhi's air more in November than in October? (step 62; follows 60-61)

    python src/62_delhi_haze_fires.py

If the same fire does more harm later in the season (cooler, calmer, shallower air), then moving burning into
November (step 60) made Delhi's air worse even with the same number of fires.

Data, 1 Oct-30 Nov, 2003-2025:
  haze   MODIS MAIAC aerosol optical depth at 550 nm (MCD19A2 C6.1, 1 km, Terra + Aqua, best quality), mean over a
         30 km disc around central Delhi, daily
  fires  MODIS fire pixels in India's Punjab + Haryana (step 60), summed over the two previous days (smoke takes about
         one to two days to reach Delhi on north-westerly winds)
  weather ERA5-Land daily: 10 m wind speed, 2 m temperature, precipitation (Delhi)
Model (days with AOD):  log AOD = a + b1 log(1+fires) + b2 log(1+fires) x November + November + weather + year effects,
with errors clustered by season. b2 > 0: a fire adds more haze in November.
Writes outputs/delhi_haze_daily.csv, outputs/delhi_haze_model.csv, figures/delhi_haze_fires.png.
"""
import sys
from pathlib import Path

import ee
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).parent))
import smoglib as S  # noqa: E402

OUT, FIG = S.R / "outputs", S.R / "figures"
OUT_TAG = ""
DELHI_XY = (77.21, 28.63)


def season(y):
    DELHI = ee.Geometry.Point(*DELHI_XY); disc = DELHI.buffer(30000); start, end = ee.Date.fromYMD(y, 10, 1), ee.Date.fromYMD(y, 12, 1)
    aod = ee.ImageCollection("MODIS/061/MCD19A2_GRANULES").filterDate(start, end).select(["Optical_Depth_055", "AOD_QA"])
    def good(i):
        q = i.select("AOD_QA"); cm = q.bitwiseAnd(7).eq(1); qa = q.rightShift(8).bitwiseAnd(15).eq(0)   # clear, best quality
        return i.select("Optical_Depth_055").multiply(0.001).updateMask(cm.And(qa)).set("day", i.date().format("YYYY-MM-dd"))
    aod = aod.map(good)
    days = ee.List.sequence(0, end.difference(start, "day").subtract(1))
    def per_day(k):
        d0 = start.advance(k, "day"); d1 = d0.advance(1, "day")
        a = aod.filterDate(d0, d1).mean().reduceRegion(ee.Reducer.mean(), disc, 1000, maxPixels=1e8).get("Optical_Depth_055")
        w = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate(d0, d1).first()
        m = w.select(["u_component_of_wind_10m", "v_component_of_wind_10m", "temperature_2m", "total_precipitation_sum"]).reduceRegion(ee.Reducer.mean(), DELHI, 11000)
        return ee.Feature(None, {"date": d0.format("YYYY-MM-dd"), "aod": a, "u": m.get("u_component_of_wind_10m"), "v": m.get("v_component_of_wind_10m"),
                                 "t2m": m.get("temperature_2m"), "rain": m.get("total_precipitation_sum")})
    out = []
    for k0 in range(0, 61, 10):                       # small requests: Earth Engine's restricted mode caps concurrency
        chunk = ee.List.sequence(k0, min(k0 + 9, end.difference(start, "day").subtract(1).getInfo()))
        for attempt in range(8):
            try:
                out += [f["properties"] for f in ee.FeatureCollection(chunk.map(per_day)).getInfo()["features"]]; break
            except ee.EEException as e:
                if "Too Many Requests" not in str(e) or attempt == 7:
                    raise
                import time; time.sleep(30 * (attempt + 1))
    return out


def season_fallback(y):
    """Same season without Earth Engine: MERRA-2 total AOD (assimilates MODIS AOD; ~50 km) over NASA OPeNDAP and
    ERA5-Land weather from the CDS point service. A different product from MAIAC: never mixed with it."""
    sys.path.insert(0, str(Path.home() / "dev/research-helpers/src"))
    from research_helpers import eodata as E
    w = E.era5_land_point(*DELHI_XY, f"{y}-10-01", f"{y}-11-30").reset_index()
    tcol = [c for c in w.columns if "time" in c.lower()][0]
    w = w.groupby(pd.to_datetime(w[tcol]).dt.normalize()).agg(u=("u10", "mean"), v=("v10", "mean"), t2m=("t2m", "mean"), rain=("tp", "max"))   # ERA5-Land accumulates through the day: the max is the daily total
    rows = []
    for day in pd.date_range(f"{y}-10-01", f"{y}-11-30"):
        try:
            a = E.merra2_aod_point(*DELHI_XY, day.strftime("%Y-%m-%d"))
        except Exception as e:
            print("  MERRA-2 missing", day.date(), type(e).__name__); a = np.nan
        r = w.loc[day] if day in w.index else None
        rows.append({"date": day, "aod": a, **({k: r[k] for k in ("u", "v", "t2m", "rain")} if r is not None else {})})
    return rows


def main():
    sys.path.insert(0, str(Path.home() / "dev/research-helpers/src"))
    from research_helpers import eodata as E
    route = "maiac" if E.ee_available() and "--merra2" not in sys.argv else "merra2"
    print("route:", route, "(MODIS MAIAC via Earth Engine)" if route == "maiac" else "(MERRA-2 + ERA5-Land, Earth Engine unavailable)", flush=True)
    if route == "maiac":
        S.init()
    f = OUT / ("delhi_haze_daily.csv" if route == "maiac" else "delhi_haze_daily_merra2.csv")
    d = pd.read_csv(f, parse_dates=["date"]) if f.exists() else pd.DataFrame()
    done = set(d.date.dt.year) if len(d) else set()
    for y in range(2003, 2026):
        if y not in done:
            rows = season(y) if route == "maiac" else season_fallback(y)
            d = pd.concat([d, pd.DataFrame(rows).assign(date=lambda x: pd.to_datetime(x.date))], ignore_index=True)
            d.to_csv(f, index=False); print("season", y, flush=True)
    global OUT_TAG
    OUT_TAG = "" if route == "maiac" else "_merra2"
    fi = pd.read_csv(OUT / "paddy_law_fires_daily.csv", parse_dates=["date"])
    fi = fi[fi.region.str.startswith("India")].groupby("date").fires.sum()
    fi = fi.reindex(pd.date_range("2003-09-15", "2025-12-15"), fill_value=0)
    lag = (fi.shift(1) + fi.shift(2)).rename("fires_lag")
    d = d.merge(lag, left_on="date", right_index=True, how="left")
    d["year"] = d.date.dt.year; d["nov"] = (d.date.dt.month == 11).astype(int); d["wind"] = np.hypot(d.u, d.v)
    d["t2m"] = d.t2m - 273.15; d["rain_mm"] = d.rain * 1000; d["lf"] = np.log1p(d.fires_lag)
    m = d.dropna(subset=["aod", "lf", "wind", "t2m"]).query("aod > 0").copy(); m["laod"] = np.log(m.aod)
    fit = smf.ols("laod ~ lf * nov + wind + t2m + rain_mm + C(year)", m).fit(cov_type="cluster", cov_kwds={"groups": m.year})
    rows = []
    for k in ("lf", "lf:nov", "nov", "wind", "t2m", "rain_mm"):
        rows.append({"term": k, "coef": fit.params[k], "ci_lo": fit.conf_int().loc[k, 0], "ci_hi": fit.conf_int().loc[k, 1], "p": fit.pvalues[k]})
    t = pd.DataFrame(rows); t["n_days"] = int(fit.nobs); t.round(4).to_csv(OUT / f"delhi_haze_model{OUT_TAG}.csv", index=False)
    print(t.round(3).to_string(index=False), "\ndays:", int(fit.nobs))
    # effect of doubling fires, October vs November, in % of AOD
    b, bn = fit.params["lf"], fit.params["lf:nov"]
    oct_pct, nov_pct = 100 * (2 ** b - 1), 100 * (2 ** (b + bn) - 1)
    print(f"doubling the previous two days' fires raises Delhi AOD by {oct_pct:.1f}% in October and {nov_pct:.1f}% in November")
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    for mo, c, lab in ((0, "#e08214", "October"), (1, "#542788", "November")):
        s = m[m.nov == mo]; bins = pd.cut(s.fires_lag, [-1, 0, 50, 200, 500, 1000, 3000, 1e5])
        g = s.groupby(bins, observed=True).aod.agg(["median", "size"])
        ax[0].plot(range(len(g)), g["median"], "-o", color=c, label=lab)
        ax[0].set_xticks(range(len(g)), [str(i).replace("(-1.0, 0.0]", "0").replace(".0", "") for i in g.index], rotation=30, fontsize=8)
    ax[0].set_xlabel("Punjab + Haryana fire pixels, previous two days"); ax[0].set_ylabel("Delhi aerosol optical depth (median)"); ax[0].legend(frameon=False)
    sy = m.groupby("year").agg(aod_nov=("aod", lambda s: s[m.loc[s.index, "nov"] == 1].mean()), aod_oct=("aod", lambda s: s[m.loc[s.index, "nov"] == 0].mean()))
    ax[1].plot(sy.index, sy.aod_oct, "-o", color="#e08214", ms=3, label="October"); ax[1].plot(sy.index, sy.aod_nov, "-o", color="#542788", ms=3, label="November")
    ax[1].axvspan(2008.5, 2009.5, color="#f0c419", alpha=.35, lw=0); ax[1].set_ylabel("Delhi mean aerosol optical depth"); ax[1].legend(frameon=False)
    for a in ax:
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
    fig.suptitle("The same smoke weighs more in November", x=.02, ha="left", fontsize=14, fontweight="bold", y=1.02)
    fig.text(.02, .955, f"Left: Delhi haze against Punjab and Haryana fires of the two days before. Model with weather and year effects ({int(fit.nobs)} days, 2003-2025):\n"
             f"doubling fires raises Delhi's aerosol optical depth by {oct_pct:.1f}% in October and {nov_pct:.1f}% in November "
             f"(difference p = {fit.pvalues['lf:nov']:.2f}). Right: October and November means by season.", fontsize=9, va="bottom", color="#333")
    fig.text(.02, -.04, ("Data: MODIS MAIAC AOD 550 nm (MCD19A2 C6.1), 30 km around central Delhi" if not OUT_TAG else "Data: MERRA-2 total AOD 550 nm (M2T1NXAER, ~50 km cell over Delhi)") + "; MODIS MOD14A1/MYD14A1 fires; ERA5-Land weather.", fontsize=7, color="#666")
    fig.savefig(FIG / f"delhi_haze_fires{OUT_TAG}.png", dpi=200, bbox_inches="tight", facecolor="white")


if __name__ == "__main__":
    main()
