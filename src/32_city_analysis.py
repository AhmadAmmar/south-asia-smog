"""City analyses from outputs/city_daily.csv and outputs/punjab_fires_daily.csv.

  1. Weather on anomalies: each variable minus its 31-day running climatology for that city and day of year, so the
     shared seasonal cycle (winter: shallow mixing layer and long NO2 lifetime together) cannot create the correlation.
  2. Surface proxy: AOD / mixing height (per km). A column spread over a shallower layer means more particles per
     cubic metre near the ground. It is a relative index, not PM2.5 in ug m-3: converting needs ground monitors
     (OpenAQ) for calibration and humidity for particle swelling.
  3. Fire to smog: Spearman correlation of daily Punjab fire detections (Aqua + Terra, daytime) with AOD and the proxy
     in Delhi and Lahore 0-5 days later, 15 Oct to 30 Nov, split by wind direction (from the north-west or not).
  4. Fire timing: detections by overpass per season.

Figures fig_anomaly_weather, fig_surface_proxy, fig_fire_lag, fig_fire_timing; outputs/*.csv.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import smoglib as S

plt.rcParams.update({"font.size": 8, "figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False})
d = pd.read_csv(S.OUT / "city_daily.csv", parse_dates=["date"])
d["doy"], d["year"], d["month"] = d.date.dt.dayofyear, d.date.dt.year, d.date.dt.month
d.loc[d.aod <= 0, "aod"] = np.nan
d["proxy"] = d.aod / (d.boundary_layer_height / 1000)
SMOG = d.month.isin([11, 12, 1])
FOCUS = ["Lahore", "Delhi", "Dhaka", "Patna", "Kolkata", "Peshawar"]


def save(fig, name):
    fig.savefig(S.FIG / f"{name}.png", bbox_inches="tight"); fig.savefig(S.FIG / f"{name}.pdf", bbox_inches="tight"); plt.close(fig)


def anomalies(g, cols):
    out = g.copy()
    for c in cols:
        clim = g.groupby("doy")[c].mean().reindex(range(1, 367))
        clim = pd.concat([clim.iloc[-15:], clim, clim.iloc[:15]]).rolling(31, center=True, min_periods=10).mean().iloc[15:-15]
        out[c] = g[c].values - clim.reindex(g.doy).values
    return out


# 1. anomaly correlations
rows = []
cols = ["no2", "aod", "proxy", "boundary_layer_height", "wind"]
for c in FOCUS:
    g = d[d.city == c].sort_values("date")
    a = anomalies(g, cols)
    for name, src in (("raw", g), ("anomaly", a)):
        s = src[SMOG.loc[src.index]]
        for v in ("no2", "aod", "proxy"):
            for w in ("boundary_layer_height", "wind"):
                ok = s[[v, w]].dropna()
                rows.append({"city": c, "series": name, "var": v, "weather": w, "rho": spearmanr(ok[v], ok[w])[0], "n": len(ok)})
corr = pd.DataFrame(rows)
corr.round(3).to_csv(S.OUT / "weather_correlations.csv", index=False)
print(corr.pivot_table(index=["city", "var"], columns=["weather", "series"], values="rho").round(2).to_string())

fig, axs = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for ax, w, t in zip(axs, ("boundary_layer_height", "wind"), ("mixing height", "10 m wind")):
    sub = corr[(corr.weather == w) & (corr.series == "anomaly")].pivot(index="city", columns="var", values="rho").reindex(FOCUS)
    sub[["no2", "aod", "proxy"]].plot.bar(ax=ax, color=["#7a3d8f", "#e08a00", "#333333"], width=0.8, rot=0)
    ax.axhline(0, color="grey", lw=0.6); ax.set_title(f"Smog-season daily anomalies: correlation with {t}")
    ax.legend(["NO₂", "AOD", "AOD / mixing height"], fontsize=7, frameon=False)
axs[0].set_ylabel("Spearman ρ (anomalies from the seasonal cycle)")
save(fig, "fig_anomaly_weather")

# 2. surface proxy annual cycles
fig, axs = plt.subplots(1, 2, figsize=(11, 4))
for c in FOCUS:
    g = d[d.city == c]
    lw = 2 if c in ("Lahore", "Delhi") else 0.9
    for ax, v in zip(axs, ("aod", "proxy")):
        cyc = g.groupby("doy")[v].median().reindex(range(1, 367)).rolling(15, center=True, min_periods=5).mean()
        ax.plot(cyc.index, cyc, lw=lw, label=c)
for ax, t in zip(axs, ("Column AOD (what the satellite sees)", "AOD per km of mixing layer (surface proxy, not PM2.5)")):
    ax.set_xticks([1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335], list("JFMAMJJASOND")); ax.set_title(t)
    ax.axvspan(305, 366, color="grey", alpha=0.1); ax.axvspan(1, 31, color="grey", alpha=0.1)
axs[1].legend(fontsize=7, frameon=False); axs[0].set_ylabel("median, 15-day smoothing")
save(fig, "fig_surface_proxy")
pk = {c: int(d[d.city == c].groupby("doy").proxy.median().rolling(15, center=True, min_periods=5).mean().idxmax()) for c in FOCUS}
print("proxy peak day of year:", pk)

# 3. fire to smog lag
f = pd.read_csv(S.OUT / "punjab_fires_daily.csv", parse_dates=["date"])
f["fires"] = f.terra_day + f.aqua_day
lag_rows = []
for c in ("Delhi", "Lahore"):
    g = d[d.city == c].set_index("date")
    nw = (g.u10 > 0) & (g.v10 < 0)                    # wind blowing towards the south-east, i.e. from the north-west
    for lag in range(0, 6):
        x = f.set_index("date").fires.copy(); x.index = x.index + pd.Timedelta(days=lag)
        j = g.join(x, how="inner")
        j = j[(j.index.month == 11) | ((j.index.month == 10) & (j.index.day >= 15))]
        for v in ("aod", "proxy"):
            for lab, m in (("all days", slice(None)), ("north-west wind", nw.reindex(j.index).fillna(False).values)):
                ok = j.loc[m, [v, "fires"]].dropna()
                lag_rows.append({"city": c, "lag": lag, "var": v, "wind": lab, "rho": spearmanr(ok[v], ok.fires)[0], "n": len(ok)})
lag = pd.DataFrame(lag_rows)
lag.round(3).to_csv(S.OUT / "fire_lag.csv", index=False)
print(lag.pivot_table(index=["city", "var", "wind"], columns="lag", values="rho").round(2).to_string())
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
for ax, c in zip(axs, ("Delhi", "Lahore")):
    for (v, w), g in lag[lag.city == c].groupby(["var", "wind"]):
        ax.plot(g.lag, g.rho, marker="o", ls="-" if v == "aod" else "--", color="#D55E00" if w == "north-west wind" else "#0072B2",
                label=f"{'AOD' if v == 'aod' else 'AOD/mixing height'}, {w}")
    ax.axhline(0, color="grey", lw=0.5); ax.set_xlabel("Days after the fires"); ax.set_title(f"{c}: Punjab fires and aerosol, 15 Oct – 30 Nov")
axs[0].set_ylabel("Spearman ρ"); axs[1].legend(fontsize=6.5, frameon=False)
save(fig, "fig_fire_lag")

# 4. fire timing
f["year"] = f.date.dt.year
t = f.groupby("year")[["terra_day", "aqua_day", "terra_night", "aqua_night"]].sum()
t.to_csv(S.OUT / "punjab_fire_timing.csv")
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
axs[0].plot(t.index, t.terra_day, "o-", label="Terra, about 10:30"); axs[0].plot(t.index, t.aqua_day, "o-", label="Aqua, about 13:30")
axs[0].set_yscale("log"); axs[0].set_ylabel("fire pixels, 15 Sep – 15 Dec"); axs[0].legend(frameon=False)
axs[0].set_title("Punjab fire detections by overpass time")
axs[1].plot(t.index, t.aqua_day / t.terra_day, "o-", color="k"); axs[1].set_ylabel("Aqua / Terra detections")
axs[1].set_title("Afternoon / morning: burning has moved later in the day")
save(fig, "fig_fire_timing")
print("written")
