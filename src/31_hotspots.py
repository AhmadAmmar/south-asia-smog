"""Hotspots and their likely sources, from the monthly grids and point-source inventories.

Method
  1. Long-term mean of each column (all months 2019-01 to 2026-10, each month weighted equally).
  2. Background = 2 degree running median; enhancement = mean - background. This removes the broad regional haze and
     keeps compact sources (a coal plant, a city, a refinery).
  3. Hotspot = connected cells whose enhancement exceeds 4 robust standard deviations (1.4826 x MAD, land and sea
     cells together); each cluster is reported at its peak cell.
  4. Attribution, nearest first within 30 km of the peak: thermal power plant >= 300 MW (WRI GPPD; coal, gas, oil),
     else a place of >= 300 000 people (Natural Earth), else "unattributed" (industry, refineries, brick kilns,
     smelters, or a source missing from the inventories).
  5. Fingerprints at each NO2 hotspot: SO2/NO2 enhancement ratio (high for coal burning without desulphurisation)
     and the winter/monsoon ratio of the NO2 enhancement.
  Fires are mapped separately: mean monthly detections in Oct-Nov (rice residue) and Apr-May (wheat residue, forest).

Writes outputs/hotspots_<var>.csv and figures fig_hotspots_<var>, fig_fingerprint, fig_fire_seasons.
These are statistical hotspots in satellite columns, not an emission inventory; attribution by distance is a lead,
not proof.
"""
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import ndimage

import smoglib as S

plt.rcParams.update({"font.size": 8, "figure.dpi": 150})
LON = S.WEST + S.RES * (np.arange(S.NX) + 0.5)
LAT = S.NORTH - S.RES * (np.arange(S.NY) + 0.5)
EXT = [S.WEST, S.EAST, S.SOUTH, S.NORTH]
PP = pd.read_csv(S.OUT / "power_plants.csv")
PP = PP[PP.fuel.isin(["Coal", "Gas", "Oil"]) & (PP.mw >= 300)]
PLACES = pd.read_csv(S.OUT / "cities_ne.csv").query("pop >= 300000")
COL = {"coal power": "#000000", "gas/oil power": "#0072B2", "city": "#D55E00", "unattributed": "#CC79A7"}


def load(var, months=None):
    """Mean of a variable's monthly grids (optionally only some months)."""
    stack = []
    for f in sorted((S.DATA / "grids" / var).glob("*.npz")):
        if months and int(f.stem[-2:]) not in months:
            continue
        a = np.load(f)["mean"].astype(float)
        a[~np.isfinite(a)] = np.nan
        stack.append(a)
    return np.nanmean(stack, axis=0)


def enhancement(a):
    """Grid minus its 21-cell median background."""
    bg = ndimage.generic_filter(np.nan_to_num(a, nan=np.nanmedian(a)), np.median, size=21, mode="nearest")
    return a - bg


def km(lon0, lat0, lon, lat):
    """Distance in km from one point to others (equirectangular)."""
    return 111.2 * np.hypot((lon - lon0) * np.cos(np.radians(lat0)), lat - lat0)


def attribute(lon, lat):
    """Likely source of a hotspot: the nearest power plant within 30 km, else the nearest city within 30 km,
    else unattributed; returns (kind, description)."""
    d = km(lon, lat, PP.lon.values, PP.lat.values)
    if len(d) and d.min() <= 30:
        p = PP.iloc[d.argmin()]
        return ("coal power" if p.fuel == "Coal" else "gas/oil power"), f"{p['name']} ({p.fuel}, {p.mw:.0f} MW, {d.min():.0f} km)"
    d = km(lon, lat, PLACES.lon.values, PLACES.lat.values)
    if d.min() <= 30:
        p = PLACES.iloc[d.argmin()]
        return "city", f"{p['name']} (pop. {p['pop'] / 1e6:.1f} M, {d.min():.0f} km)"
    return "unattributed", ""


def hotspots(var, k=4.0, top=30):
    """Cells whose enhancement exceeds k robust standard deviations (MAD x 1.4826), top cells attributed."""
    a = load(var)
    e = enhancement(a)
    sd = 1.4826 * np.nanmedian(np.abs(e - np.nanmedian(e)))
    lab, n = ndimage.label(np.nan_to_num(e) > k * sd)
    rows = []
    for i in range(1, n + 1):
        m = lab == i
        j = np.nanargmax(np.where(m, e, -np.inf))
        y, x = np.unravel_index(j, e.shape)
        cls, what = attribute(LON[x], LAT[y])
        rows.append({"lon": round(LON[x], 2), "lat": round(LAT[y], 2), "peak": a[y, x], "enhancement": e[y, x],
                     "z": e[y, x] / sd, "cells": int(m.sum()), "class": cls, "nearest": what, "y": y, "x": x})
    h = pd.DataFrame(rows).sort_values("enhancement", ascending=False).head(top).reset_index(drop=True)
    return a, e, sd, h


def axes_map(ax):
    """Map axes over the study extent with coastlines and borders."""
    ax.set_extent(EXT, ccrs.PlateCarree())
    ax.add_feature(cfeature.COASTLINE.with_scale("10m"), lw=0.4)
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), lw=0.3, edgecolor="#555")


def fig_hot(var, e, sd, h):
    """Figure: enhancement map with hotspots and their table."""
    fig = plt.figure(figsize=(12, 7.5))
    ax = fig.add_axes([0.02, 0.05, 0.6, 0.9], projection=ccrs.PlateCarree())
    axes_map(ax)
    im = ax.imshow(e / sd, extent=EXT, origin="upper", transform=ccrs.PlateCarree(), cmap="RdBu_r", vmin=-8, vmax=8)
    plt.colorbar(im, ax=ax, shrink=0.6, label="Enhancement over 2° background (robust standard deviations)")
    for i, r in h.iterrows():
        ax.scatter(r.lon, r.lat, s=60, facecolor="none", edgecolor=COL[r["class"]], lw=1.4, transform=ccrs.PlateCarree())
        ax.text(r.lon + 0.25, r.lat + 0.15, str(i + 1), fontsize=6.5, transform=ccrs.PlateCarree())
    for c, col in COL.items():
        ax.scatter([], [], s=50, facecolor="none", edgecolor=col, lw=1.4, label=c)
    ax.legend(loc="lower left", fontsize=7, frameon=True)
    ax.set_title(f"{S.VARS[var][4]} hotspots, 2019–2026 mean: top {len(h)} by enhancement")
    tx = fig.add_axes([0.64, 0.05, 0.35, 0.9]); tx.axis("off")
    lines = [f"{i + 1:>2}. {r.lat:5.2f}N {r.lon:5.2f}E  +{r.enhancement:.0f}  {r['class']}" + (f"\n      {r.nearest[:52]}" if r.nearest else "")
             for i, r in h.iterrows()]
    tx.text(0, 1, f"Peak enhancement in {S.VARS[var][3]}\n\n" + "\n".join(lines), va="top", family="monospace", fontsize=6)
    fig.savefig(S.FIG / f"fig_hotspots_{var}.png", bbox_inches="tight"); fig.savefig(S.FIG / f"fig_hotspots_{var}.pdf", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    res = {}
    for var in ("no2", "so2"):   # CO and HCHO: the 2 degree background fails at the Himalayan front (column falls with surface pressure), so their "hotspots" are terrain edges
        a, e, sd, h = hotspots(var)
        res[var] = (a, e, sd, h)
        h.drop(columns=["y", "x"]).round(2).to_csv(S.OUT / f"hotspots_{var}.csv", index=False)
        fig_hot(var, e, sd, h)
        print(var, "robust sd", round(sd, 2), h["class"].value_counts().to_dict())
        print(h[["lat", "lon", "enhancement", "z", "class", "nearest"]].head(12).round(1).to_string())

    # fingerprints at NO2 hotspots
    h = res["no2"][3].copy()
    eso2 = res["so2"][1]
    win, mon = enhancement(load("no2", (11, 12, 1))), enhancement(load("no2", (7, 8)))
    box = lambda g, r: np.nanmean(g[max(r.y - 1, 0):r.y + 2, max(r.x - 1, 0):r.x + 2])
    h["so2_no2"] = [box(eso2, r) / box(res["no2"][1], r) for _, r in h.iterrows()]
    h["winter_monsoon"] = [box(win, r) / box(mon, r) for _, r in h.iterrows()]
    h.drop(columns=["y", "x"]).round(3).to_csv(S.OUT / "hotspots_no2.csv", index=False)
    fig, ax = plt.subplots(figsize=(7, 5))
    for c, g in h.groupby("class"):
        ax.scatter(g.winter_monsoon, g.so2_no2, s=20 + g.enhancement, color=COL[c], label=c, alpha=0.8)
    for i, r in h.iterrows():
        ax.annotate(str(i + 1), (r.winter_monsoon, r.so2_no2), fontsize=6, xytext=(3, 2), textcoords="offset points")
    ax.axhline(0, color="grey", lw=0.5)
    ax.set_xlabel("NO₂ enhancement, winter / monsoon"); ax.set_ylabel("SO₂ / NO₂ enhancement ratio")
    ax.set_title("Source fingerprints of the NO₂ hotspots (numbers as in fig_hotspots_no2)"); ax.legend(fontsize=7, frameon=False)
    fig.savefig(S.FIG / "fig_fingerprint.png", bbox_inches="tight"); fig.savefig(S.FIG / "fig_fingerprint.pdf", bbox_inches="tight"); plt.close(fig)
    print(h.groupby("class")[["so2_no2", "winter_monsoon"]].median().round(2))

    # fire seasons
    fig, axs = plt.subplots(1, 2, figsize=(12, 5), subplot_kw={"projection": ccrs.PlateCarree()})
    for ax, (mm, t) in zip(axs, (((10, 11), "October–November (rice residue)"), ((3, 4, 5), "March–May (wheat residue, forests)"))):
        st = []
        for f in sorted((S.DATA / "grids" / "fire").glob("*.npz")):
            if int(f.stem[-2:]) in mm:
                n = np.load(f)["n"].astype(float); n[~np.isfinite(n)] = 0; st.append(n)
        m = np.mean(st, axis=0)
        axes_map(ax)
        im = ax.imshow(np.where(m > 0.2, m, np.nan), extent=EXT, origin="upper", transform=ccrs.PlateCarree(), cmap="hot_r",
                       norm=plt.matplotlib.colors.LogNorm(0.2, 100))
        ax.set_title(t)
    plt.colorbar(im, ax=axs, shrink=0.7, label="Fire detections per 0.1° cell per month (mean, log scale)")
    fig.savefig(S.FIG / "fig_fire_seasons.png", bbox_inches="tight"); fig.savefig(S.FIG / "fig_fire_seasons.pdf", bbox_inches="tight"); plt.close(fig)
    print("written")
