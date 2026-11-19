"""Maps and charts from the monthly grids (data/grids), whatever has been downloaded so far.

  fig_smog_from_space   one smog-season month (default November of the latest complete year): AOD, UV aerosol
                        index, NO2, CO, HCHO and fire detections side by side
  fig_season_<var>      smog season (Nov-Jan) against monsoon (Jul-Aug) and their ratio
  fig_monthly_<var>     the twelve-month climatology
  fig_hovmoller         longitude against time across the Indo-Gangetic Plain (24-32 N): the smog season every winter
  fig_index             a satellite smog index: mean of standardised AOD, NO2 and CO (not an air quality index)
  fig_trend_<var>       Sen slope of the smog-season mean across winters, with the share of winters available
Writes outputs/grid_summary.csv (regional means per month and variable).
"""
import sys
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import smoglib as S

plt.rcParams.update({"font.size": 8, "figure.dpi": 150})
LON = S.WEST + S.RES * (np.arange(S.NX) + 0.5)
LAT = S.NORTH - S.RES * (np.arange(S.NY) + 0.5)
EXT = [S.WEST, S.EAST, S.SOUTH, S.NORTH]
BORDERS = cfeature.NaturalEarthFeature("cultural", "admin_0_boundary_lines_land", "10m", facecolor="none")
CMAP = {"no2": "magma_r", "aod": "YlOrBr", "uvai": "PuOr_r", "co": "viridis", "hcho": "GnBu", "so2": "RdPu", "o3": "cividis", "fire": "hot_r"}
SMOG, MONSOON = (11, 12, 1), (7, 8)


def load(var):
    """Monthly grids of a variable: {(year, month): (mean, count)}."""
    out = {}
    for f in sorted((S.DATA / "grids" / var).glob("*.npz")):
        y, m = map(int, f.stem.split("-"))
        z = np.load(f)
        a, n = z["mean"].astype(float), z["n"].astype(float)
        bad = ~np.isfinite(a)                 # cells with no valid day arrive as -inf (masked pixels), not NaN
        a[bad], n[bad | ~np.isfinite(n)] = np.nan, 0
        out[(y, m)] = (a, n)
    return out


def label(var):
    """Title and units of a variable."""
    if var == "fire":
        return "Fire detections per cell per month", ""
    return S.VARS[var][4], S.VARS[var][3]


def axes_map(ax, title):
    """Map axes over the study extent with coastlines and borders."""
    ax.set_extent(EXT, ccrs.PlateCarree())
    ax.add_feature(cfeature.COASTLINE.with_scale("10m"), lw=0.4)
    ax.add_feature(BORDERS, lw=0.3, edgecolor="#555")
    ax.set_title(title, fontsize=8)


def draw(ax, a, var, vmin=None, vmax=None, cmap=None, title="", cb=True):
    """Draw a grid on map axes, colour range 2nd-98th percentile unless given, with a colour bar."""
    axes_map(ax, title)
    vmin = np.nanpercentile(a, 2) if vmin is None else vmin
    vmax = np.nanpercentile(a, 98) if vmax is None else vmax
    im = ax.imshow(a, extent=EXT, origin="upper", transform=ccrs.PlateCarree(), cmap=cmap or CMAP.get(var, "viridis"), vmin=vmin, vmax=vmax)
    if cb:
        name, unit = label(var)
        plt.colorbar(im, ax=ax, shrink=0.7, pad=0.02, label=unit or name)
    return im


def season_mean(g, months, years=None):
    """Mean of the monthly grids in the given months (and years), or None."""
    stack = [v[0] for (y, m), v in g.items() if m in months and (years is None or y in years)]
    return np.nanmean(stack, axis=0) if stack else None


def winter_mean(g, w):
    """Smog season ending in January of year w+1: Nov and Dec of w, Jan of w+1."""
    keys = [(w, 11), (w, 12), (w + 1, 1)]
    if not all(k in g for k in keys):
        return None
    return np.nanmean([g[k][0] for k in keys], axis=0)


def save(fig, name):
    """Save a figure as PNG and PDF."""
    fig.savefig(S.FIG / f"{name}.png", bbox_inches="tight"); fig.savefig(S.FIG / f"{name}.pdf", bbox_inches="tight"); plt.close(fig)


def fig_smog_from_space(G, y=None, m=11):
    """Figure: AOD, UV aerosol index, NO2, CO, HCHO and fires in one month (default November of the latest year)."""
    y = y or max(yy for (yy, mm) in G["no2"] if mm == m)
    vs = [v for v in ("aod", "uvai", "no2", "co", "hcho", "fire") if v in G and (y, m) in G[v]]
    fig, axs = plt.subplots(2, 3, figsize=(13, 8), subplot_kw={"projection": ccrs.PlateCarree()})
    for ax, v in zip(axs.flat, vs):
        a = G[v][(y, m)][1] if v == "fire" else G[v][(y, m)][0]
        if v == "fire":
            a = np.where(a > 0, a, np.nan)
            draw(ax, a, v, 1, np.nanpercentile(a, 99), title=label(v)[0])
        elif v == "uvai":
            draw(ax, a, v, -2, 2, title=label(v)[0])
        else:
            draw(ax, a, v, title=label(v)[0])
    for ax in axs.flat[len(vs):]:
        ax.set_visible(False)
    part = f" 1–{pd.Timestamp.today() - pd.Timedelta(days=1):%d}, month in progress" if (y, m) == (pd.Timestamp.today().year, pd.Timestamp.today().month) else ""
    fig.suptitle(f"Seeing smog from space: South Asia, {pd.Timestamp(y, m, 1):%B %Y}{part} (means, Sentinel-5P, MODIS MAIAC, FIRMS)", fontsize=10)
    save(fig, "fig_smog_from_space")
    return y


def fig_season(G, var):
    """Figure: smog-season mean against monsoon mean of a variable, and their difference."""
    g = G[var]
    a, b = season_mean(g, SMOG), season_mean(g, MONSOON)
    if a is None or b is None:
        return
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.2), subplot_kw={"projection": ccrs.PlateCarree()})
    lo, hi = np.nanpercentile(np.r_[a.ravel(), b.ravel()], [2, 98])
    if var == "uvai":
        lo, hi = -1.5, 1.5
    draw(axs[0], a, var, lo, hi, title=f"{label(var)[0]}: smog season (Nov–Jan)")
    draw(axs[1], b, var, lo, hi, title="Monsoon (Jul–Aug)")
    if var == "uvai":
        draw(axs[2], a - b, var, -1.5, 1.5, "RdBu_r", "Smog season minus monsoon")
    else:
        r = np.where(b > 0, a / b, np.nan)
        draw(axs[2], np.log2(r), var, -2, 2, "RdBu_r", "Ratio smog season / monsoon (log2: 1 = double)", cb=False)
        plt.colorbar(axs[2].images[0], ax=axs[2], shrink=0.7, label="log2 ratio")
    save(fig, f"fig_season_{var}")


def fig_monthly(G, var):
    """Figure: the twelve monthly climatology maps of a variable."""
    g = G[var]
    fig, axs = plt.subplots(3, 4, figsize=(14, 9), subplot_kw={"projection": ccrs.PlateCarree()})
    clim = {m: season_mean(g, (m,)) for m in range(1, 13)}
    allv = np.concatenate([c.ravel() for c in clim.values() if c is not None])
    lo, hi = (-1.5, 1.5) if var == "uvai" else np.nanpercentile(allv, [2, 98])
    for ax, m in zip(axs.flat, range(1, 13)):
        if clim[m] is not None:
            draw(ax, clim[m], var, lo, hi, title=pd.Timestamp(2001, m, 1).strftime("%B"), cb=False)
    fig.colorbar(axs.flat[0].images[0], ax=axs, shrink=0.5, label=" ".join(label(var)))
    fig.suptitle(f"{label(var)[0]}: mean of each calendar month, {min(y for y, _ in g)}–{max(y for y, _ in g)}", fontsize=10)
    save(fig, f"fig_monthly_{var}")


def fig_hovmoller(G, vars_=("no2", "aod")):
    """Figure: time-longitude diagram of variables averaged over 24-32 deg N."""
    band = (LAT >= 24) & (LAT <= 32)
    fig, axs = plt.subplots(1, len(vars_), figsize=(6 * len(vars_), 7), sharey=True)
    for ax, var in zip(np.atleast_1d(axs), vars_):
        g = G[var]
        keys = sorted(g)
        H = np.array([np.nanmean(g[k][0][band], axis=0) for k in keys])
        lo, hi = np.nanpercentile(H, [2, 98])
        im = ax.imshow(H, aspect="auto", cmap=CMAP[var], vmin=lo, vmax=hi, extent=[S.WEST, S.EAST, len(keys), 0])
        ax.set_yticks([i for i, k in enumerate(keys) if k[1] == 1], [str(k[0]) for k in keys if k[1] == 1])
        ax.set_xlim(66, 92); ax.set_xlabel("Longitude (°E)")
        for x, name in ((74.34, "Lahore"), (77.21, "Delhi"), (85.14, "Patna"), (88.36, "Kolkata")):
            ax.axvline(x, color="w", lw=0.5, ls=":"); ax.text(x, -0.5, name, rotation=90, fontsize=6, ha="center", va="bottom")
        plt.colorbar(im, ax=ax, label=" ".join(label(var)), shrink=0.6)
        ax.set_title(f"{label(var)[0]}, mean over 24–32° N", fontsize=8, pad=30)
    np.atleast_1d(axs)[0].set_ylabel("Month (tick = January)")
    save(fig, "fig_hovmoller")


def fig_index(G, y=None, m=11):
    """Satellite smog index: for each variable, standardise every cell by the whole region's monthly distribution
    over all months (z = (x - mean) / sd); the index is the mean z of AOD, NO2 and CO. It says where all three
    are high together. It is not an air quality index: these are columns, not surface concentrations."""
    vs = [v for v in ("aod", "no2", "co") if v in G]
    y = y or max(yy for (yy, mm) in G["no2"] if mm == m)
    zs = []
    for v in vs:
        allm = np.array([a for a, _ in G[v].values()])
        mu, sd = np.nanmean(allm), np.nanstd(allm)
        zs.append((G[v][(y, m)][0] - mu) / sd)
    idx = np.nanmean(zs, axis=0)
    fig, ax = plt.subplots(figsize=(8, 6.5), subplot_kw={"projection": ccrs.PlateCarree()})
    draw(ax, idx, "index", -1, 3, "inferno_r", f"Satellite smog index (mean standard score of {', '.join(v.upper() for v in vs)}), {pd.Timestamp(y, m, 1):%B %Y}", cb=False)
    plt.colorbar(ax.images[0], ax=ax, shrink=0.7, label="standard deviations above the regional all-month mean")
    for c, (x, yy) in S.CITIES.items():
        ax.plot(x, yy, "o", ms=2.5, color="c", transform=ccrs.PlateCarree()); ax.text(x + 0.3, yy, c, fontsize=6, transform=ccrs.PlateCarree())
    save(fig, "fig_index")


def fig_trend(G, var):
    """Figure: Theil-Sen trend of November values of a variable per cell."""
    from scipy.stats import theilslopes
    g = G[var]
    winters = sorted({y for (y, m) in g if m == 11})
    W = [(w, winter_mean(g, w)) for w in winters]
    W = [(w, a) for w, a in W if a is not None]
    if len(W) < 4:
        return
    yrs = np.array([w for w, _ in W]); A = np.array([a for _, a in W])
    slope = np.full(A.shape[1:], np.nan)
    ok = np.isfinite(A).sum(0) >= len(yrs) - 1
    for i, j in zip(*np.nonzero(ok)):
        v = A[:, i, j]; f = np.isfinite(v)
        slope[i, j] = theilslopes(v[f], yrs[f])[0]
    rel = 100 * slope / np.nanmean(A, 0)
    fig, ax = plt.subplots(figsize=(8, 6.5), subplot_kw={"projection": ccrs.PlateCarree()})
    draw(ax, rel, var, -10, 10, "RdBu_r", f"{label(var)[0]}: trend of the smog-season mean, winters {yrs[0]}/{str(yrs[0] + 1)[2:]}–{yrs[-1]}/{str(yrs[-1] + 1)[2:]} ({len(yrs)} winters)", cb=False)
    plt.colorbar(ax.images[0], ax=ax, shrink=0.7, label="% per year (Sen slope)")
    save(fig, f"fig_trend_{var}")


if __name__ == "__main__":
    have = [v for v in [*S.VARS, "fire"] if (S.DATA / "grids" / v).exists()]
    G = {v: load(v) for v in have}
    G = {v: g for v, g in G.items() if g}
    rows = []
    for v, g in G.items():
        for (y, m), (a, n) in g.items():
            rows.append({"var": v, "year": y, "month": m, "region_mean": float(np.nanmean(np.where(n > 0, a, np.nan)) if v != "fire" else np.nansum(n)),
                         "valid_share": float(np.isfinite(a).mean())})
    pd.DataFrame(rows).sort_values(["var", "year", "month"]).to_csv(S.OUT / "grid_summary.csv", index=False)
    print({v: len(g) for v, g in G.items()})
    if "no2" in G:
        print("smog-from-space month:", fig_smog_from_space(G))
    for v in G:
        if v != "fire":
            fig_season(G, v); fig_monthly(G, v); fig_trend(G, v)
    if "no2" in G and "aod" in G:
        fig_hovmoller(G); fig_index(G)
    print("figures:", sorted(p.name for p in S.FIG.glob("*.png")))
