"""Charts from outputs/city_daily.csv.

  fig_city_cycle       mean annual cycle (by day of year, 15-day smoothing) of NO2 and AOD for each city
  fig_calendar_<city>  smog calendar: day of year against year, coloured by AOD (and NO2)
  fig_weather          AOD against boundary layer height and wind in the smog season, Lahore and Delhi
Writes outputs/city_season_summary.csv: smog season against monsoon for every city and variable.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import smoglib as S

plt.rcParams.update({"font.size": 8, "figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False})
d = pd.read_csv(S.OUT / "city_daily.csv", parse_dates=["date"])
d["doy"] = d.date.dt.dayofyear
d["year"] = d.date.dt.year
d["month"] = d.date.dt.month
d["season"] = np.where(d.month.isin([11, 12, 1]), "smog", np.where(d.month.isin([7, 8]), "monsoon", "other"))
VARS = [v for v in S.VARS if v in d]


def save(fig, name):
    fig.savefig(S.FIG / f"{name}.png", bbox_inches="tight"); fig.savefig(S.FIG / f"{name}.pdf", bbox_inches="tight"); plt.close(fig)


rows = []
for c, g in d.groupby("city"):
    for v in VARS:
        s, m = g.loc[g.season == "smog", v].mean(), g.loc[g.season == "monsoon", v].mean()
        rows.append({"city": c, "var": v, "smog_mean": s, "monsoon_mean": m, "ratio": s / m if m else np.nan,
                     "smog_valid_days_pct": 100 * g.loc[g.season == "smog", v].notna().mean()})
summ = pd.DataFrame(rows)
summ.round(3).to_csv(S.OUT / "city_season_summary.csv", index=False)
print(summ.pivot(index="city", columns="var", values="ratio").round(2).to_string())

# annual cycles
fig, axs = plt.subplots(1, 2, figsize=(12, 4.5))
for ax, v in zip(axs, ("no2", "aod")):
    for c, g in d.groupby("city"):
        cyc = g.groupby("doy")[v].mean().reindex(range(1, 367))
        sm = cyc.rolling(15, center=True, min_periods=5).mean()
        lw = 2 if c in ("Lahore", "Delhi") else 0.9
        ax.plot(sm.index, sm, lw=lw, label=c)
    ax.set_xticks([1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335], list("JFMAMJJASOND"))
    ax.axvspan(305, 366, color="grey", alpha=0.1); ax.axvspan(1, 31, color="grey", alpha=0.1)
    ax.set_title(f"{S.VARS[v][4]}: mean annual cycle (grey = smog season)"); ax.set_ylabel(S.VARS[v][3] or v.upper())
axs[1].legend(fontsize=6.5, ncol=2, frameon=False)
save(fig, "fig_city_cycle")

# smog calendars
for c in ("Lahore", "Delhi", "Dhaka"):
    g = d[d.city == c]
    fig, axs = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
    for ax, v in zip(axs, ("aod", "no2")):
        P = g.pivot_table(index="year", columns="doy", values=v)
        lo, hi = np.nanpercentile(P.values, [2, 98])
        im = ax.imshow(P.values, aspect="auto", cmap="magma_r", interpolation="nearest", vmin=lo, vmax=hi, extent=[0.5, P.columns.max() + 0.5, P.index.max() + 0.5, P.index.min() - 0.5])
        plt.colorbar(im, ax=ax, label=S.VARS[v][3] or v.upper(), pad=0.01)
        ax.set_ylabel("Year"); ax.set_title(f"{c}: {S.VARS[v][4]}, every day (white = no valid retrieval)")
    axs[1].set_xticks([1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335], list("JFMAMJJASOND"))
    save(fig, f"fig_calendar_{c.lower()}")

# weather
if "boundary_layer_height" in d:
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    for c, col in (("Lahore", "#D55E00"), ("Delhi", "#0072B2")):
        g = d[(d.city == c) & (d.season == "smog")].dropna(subset=["aod", "boundary_layer_height", "wind"]).query("aod > 0")
        axs[0].scatter(g.boundary_layer_height, g.aod, s=5, alpha=0.5, color=col, label=f"{c} (r = {np.corrcoef(np.log(g.boundary_layer_height), np.log(g.aod))[0, 1]:.2f}, log-log)")
        axs[1].scatter(g.wind, g.aod, s=5, alpha=0.5, color=col, label=f"{c} (r = {np.corrcoef(g.wind, np.log(g.aod))[0, 1]:.2f})")
    axs[0].set_xscale("log"); axs[0].set_yscale("log"); axs[1].set_yscale("log")
    axs[0].set_xlabel("Daily mean boundary layer height (m)"); axs[1].set_xlabel("Daily mean 10 m wind speed (m/s)")
    for ax in axs:
        ax.set_ylabel("AOD"); ax.legend(fontsize=7, frameon=False)
    fig.suptitle("Smog season (Nov–Jan) days: column AOD against ERA5 mixing height and wind")
    save(fig, "fig_weather")
print("written")
