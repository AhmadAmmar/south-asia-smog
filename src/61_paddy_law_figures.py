"""Figures and statistics for step 60: groundwater, the 2009 paddy law, and the timing of stubble burning.

    python src/61_paddy_law_figures.py      (after 60_paddy_law_fires.py and south-asia-groundwater step 03)

Figure 1 (three panels, India's Punjab + Haryana against Pakistan's Punjab):
  a groundwater storage, GRACE ensemble mean (south-asia-groundwater, annual mean of the monthly anomalies, cm)
  b median burning date per season (day by which half of the 15 Sep-15 Dec MODIS fire pixels had burnt)
  c share of the season's fires that burn in November or later
Figure 2: the season's fire curve (cumulative share by date), mean of 2003-2008 vs 2010-2025, both regions.
Statistics: before/after means; a segmented regression of the median date (trend + step at 2010) with
autocorrelation-robust errors, for each region and for the India-Pakistan gap.
Writes figures/paddy_law_groundwater_fires.png, figures/paddy_law_fire_curves.png, outputs/paddy_law_stats.csv.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

R = Path(__file__).resolve().parents[1]; OUT, FIG = R / "outputs", R / "figures"
GW = Path.home() / "dev/south-asia-groundwater/outputs/units_monthly.csv"
IN, PK = "India: Punjab + Haryana", "Pakistan: Punjab"
COL = {IN: "#b2182b", PK: "#2166ac"}
GW_UNIT = {IN: "Indian Punjab, Haryana, Delhi", PK: "Pakistan Punjab"}


def pv(p):
    return "p < 0.01" if p < 0.01 else f"p = {p:.2f}"


def doy_label(d):
    return pd.Timestamp(2021, 1, 1) + pd.Timedelta(days=int(round(d)) - 1)


def stats(t):
    rows = []
    for r, g in t.groupby("region"):
        g = g.set_index("year").sort_index()
        X = pd.DataFrame({"t": g.index - 2009, "post": (g.index >= 2010).astype(int)})
        m = sm.OLS(g.d50.values, sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
        rows.append({"series": r, "median_day_2003_2008": g.loc[:2008].d50.mean(), "median_day_2010_2025": g.loc[2010:].d50.mean(),
                     "nov_share_2003_2008": g.loc[:2008].share_nov.mean(), "nov_share_2010_2025": g.loc[2010:].share_nov.mean(),
                     "trend_days_per_yr": m.params["t"], "step_2010_days": m.params["post"], "step_p": m.pvalues["post"]})
    w = t.pivot(index="year", columns="region", values="d50"); gap = w[IN] - w[PK]
    X = pd.DataFrame({"t": gap.index - 2009, "post": (gap.index >= 2010).astype(int)})
    m = sm.OLS(gap.values, sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
    rows.append({"series": "gap India - Pakistan", "median_day_2003_2008": gap.loc[:2008].mean(), "median_day_2010_2025": gap.loc[2010:].mean(),
                 "trend_days_per_yr": m.params["t"], "step_2010_days": m.params["post"], "step_p": m.pvalues["post"]})
    s = pd.DataFrame(rows); s.round(3).to_csv(OUT / "paddy_law_stats.csv", index=False); print(s.round(2).to_string(index=False))
    return s


def fig1(t, s):
    g = pd.read_csv(GW); g = g[g.stores != "CLSM"]; g["year"] = g.month.str[:4].astype(int)
    fig, ax = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    for r in (IN, PK):
        a = g[g.unit == GW_UNIT[r]].groupby("year").gwsa_cm.mean()
        ax[0].plot(a.index, a.values, "-o", ms=3, color=COL[r], label=r)
        x = t[t.region == r].sort_values("year")
        ax[1].plot(x.year, x.d50, "-o", ms=4, color=COL[r]); ax[2].plot(x.year, 100 * x.share_nov, "-o", ms=4, color=COL[r])
    for a in ax:
        a.axvspan(2008.5, 2009.5, color="#f0c419", alpha=.35, lw=0)
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
    ax[0].text(2009.6, ax[0].get_ylim()[1] * .9, "2008 ordinance, 2009 Act:\nno paddy transplanting before mid-June", fontsize=8, va="top")
    ax[0].set_ylabel("groundwater storage\nanomaly (cm of water)"); ax[0].legend(frameon=False, fontsize=9)
    yt = [288, 296, 304, 312, 320, 328]; ax[1].set_yticks(yt, [doy_label(d).strftime("%d %b") for d in yt]); ax[1].set_ylabel("median burning date")
    ax[2].set_ylabel("fires in November\nor later (%)"); ax[2].set_xlabel("season")
    i = s.set_index("series")
    ax[1].set_title(f"India: {doy_label(i.loc[IN, 'median_day_2003_2008']):%d %b} before, {doy_label(i.loc[IN, 'median_day_2010_2025']):%d %b} after; "
                    f"trend {i.loc[IN, 'trend_days_per_yr']:+.1f} days/yr already before 2009, step at the law {i.loc[IN, 'step_2010_days']:+.1f} days ({pv(i.loc[IN, 'step_p'])})",
                    fontsize=8.5, loc="left")
    fig.suptitle("Saving groundwater, burning later: Punjab, 2003-2025", x=.02, ha="left", fontsize=14, fontweight="bold", y=.995)
    fig.text(.02, .955, "Punjab and Haryana delayed rice transplanting to cut groundwater pumping. The rice harvest, and the burning of its stubble, moved\n"
             "towards November, when cooler, stiller air traps smoke over the plains. Pakistan's Punjab, with the same crops and no such law, moved earlier.\n"
             f"The shift began before the law. India's date steps {i.loc[IN, 'step_2010_days']:+.1f} days at the law on top of its trend ({pv(i.loc[IN, 'step_p'])}), but measured against\n"
             f"Pakistan's Punjab the step is {i.loc['gap India - Pakistan', 'step_2010_days']:+.1f} days ({pv(i.loc['gap India - Pakistan', 'step_p'])}): the law's own effect cannot be separated from the longer trend.",
             fontsize=9, va="top", color="#333")
    ax[0].axvspan(2017.5, 2018.5, color="#dddddd", lw=0); ax[0].text(2018.6, 12, "gap between\nGRACE missions", fontsize=7, color="#666")
    fig.text(.02, .005, "Data: MODIS Terra and Aqua active fires (MOD14A1/MYD14A1 C6.1), 15 Sep-15 Dec; GRACE/GRACE-FO ensemble (south-asia-groundwater); FAO GAUL 2015.",
             fontsize=7, color="#666")
    fig.subplots_adjust(top=.85, bottom=.06, hspace=.18)
    fig.savefig(FIG / "paddy_law_groundwater_fires.png", dpi=200, facecolor="white"); plt.close(fig)


def fig2(d):
    d = d.copy(); d["year"] = d.date.dt.year; d["doy"] = d.date.dt.dayofyear
    fig, ax = plt.subplots(figsize=(9, 5))
    for r in (IN, PK):
        for (a, b), ls, lab in (((2003, 2008), "--", "2003-2008"), ((2010, 2025), "-", "2010-2025")):
            x = d[(d.region == r) & d.year.between(a, b)].groupby(["year", "doy"]).fires.sum().reset_index()
            c = x.groupby("year").apply(lambda g: g.set_index("doy").fires.reindex(range(258, 351), fill_value=0).cumsum() / max(g.fires.sum(), 1)).mean()
            ax.plot(c.index, 100 * c.values, ls, color=COL[r], label=f"{r}, {lab}")
    ax.axvline(305, color="#999", lw=.8); ax.text(306, 5, "1 November", fontsize=8, color="#666")
    xt = [258, 274, 288, 305, 319, 335, 349]; ax.set_xticks(xt, [doy_label(v).strftime("%d %b") for v in xt])
    ax.set_ylabel("share of the season's fires burnt (%)"); ax.legend(frameon=False, fontsize=8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.suptitle("The burning season moved into November in India's Punjab", x=.02, ha="left", fontweight="bold", fontsize=12)
    fig.text(.02, .005, "Data: MODIS MOD14A1/MYD14A1 C6.1 fire pixels, mean cumulative curve over the seasons in each period.", fontsize=7, color="#666")
    fig.savefig(FIG / "paddy_law_fire_curves.png", dpi=200, bbox_inches="tight", facecolor="white"); plt.close(fig)


def main():
    t = pd.read_csv(OUT / "paddy_law_fire_timing.csv"); d = pd.read_csv(OUT / "paddy_law_fires_daily.csv", parse_dates=["date"])
    s = stats(t); fig1(t, s); fig2(d); print("figures written")


if __name__ == "__main__":
    main()
