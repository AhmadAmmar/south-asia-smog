"""Animation of one smog episode, day by day: AOD, NO2 and fire detections over the Indo-Gangetic Plain.

    python src/40_episode_animation.py data/episode/2024-10-20_2024-11-30.npz

Writes figures/episode_<start>_<end>.gif and a still of the worst day (highest plain-mean AOD) as
figures/fig_episode_peak_<year>.png. Days without a valid retrieval stay blank (clouds, fog, or no overpass); nothing is
filled in.
"""
import sys

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter

import smoglib as S

plt.rcParams.update({"font.size": 8, "figure.dpi": 110})
f = sys.argv[1] if len(sys.argv) > 1 else str(S.DATA / "episode" / "2024-10-20_2024-11-30.npz")
z = np.load(f)
dates, ext = z["dates"], list(z["extent"])
A, N, F = z["aod"], z["no2"], z["fire"]
CITY = {k: v for k, v in S.CITIES.items() if ext[0] <= v[0] <= ext[1] and ext[2] <= v[1] <= ext[3]}

fig, axs = plt.subplots(1, 2, figsize=(12, 4.2), subplot_kw={"projection": ccrs.PlateCarree()})
ims = []
for ax, arr, cmap, lim, lab in ((axs[0], A, "YlOrBr", (0, 2.0), "AOD 550 nm (MAIAC)"),
                                (axs[1], N, "magma_r", (0, 150), "Tropospheric NO₂ (µmol m⁻²)")):
    ax.set_extent(ext, ccrs.PlateCarree())
    ax.add_feature(cfeature.COASTLINE.with_scale("10m"), lw=0.4); ax.add_feature(cfeature.BORDERS.with_scale("10m"), lw=0.3)
    im = ax.imshow(arr[0], extent=ext, origin="upper", transform=ccrs.PlateCarree(), cmap=cmap, vmin=lim[0], vmax=lim[1])
    plt.colorbar(im, ax=ax, shrink=0.75, label=lab); ims.append(im)
    for c, (x, y) in CITY.items():
        ax.plot(x, y, "o", ms=2.5, color="c", transform=ccrs.PlateCarree()); ax.text(x + 0.2, y + 0.2, c, fontsize=6, transform=ccrs.PlateCarree())
fy, fx = np.nonzero(F[0] > 0)
lat = ext[3] - S.RES * (np.arange(A.shape[1]) + 0.5); lon = ext[0] + S.RES * (np.arange(A.shape[2]) + 0.5)
sc = axs[0].scatter([], [], s=3, color="red", transform=ccrs.PlateCarree(), label="fire detections")
axs[0].legend(loc="lower left", fontsize=6)
title = fig.suptitle("")


def frame(i):
    ims[0].set_data(A[i]); ims[1].set_data(N[i])
    yy, xx = np.nonzero(np.nan_to_num(F[i]) > 0)
    sc.set_offsets(np.c_[lon[xx], lat[yy]] if len(xx) else np.empty((0, 2)))
    title.set_text(f"Smog episode over the Indo-Gangetic Plain: {dates[i]}  (blank = no valid retrieval)")
    return ims + [sc, title]


out = S.FIG / f"episode_{dates[0]}_{dates[-1]}.gif"
FuncAnimation(fig, frame, frames=len(dates), blit=False).save(out, writer=PillowWriter(fps=3))
plain = (slice(int((ext[3] - 32) / S.RES), int((ext[3] - 25) / S.RES)), slice(int((73 - ext[0]) / S.RES), int((88 - ext[0]) / S.RES)))
m = [np.nanmean(a[plain]) if np.isfinite(a[plain]).mean() > 0.3 else np.nan for a in A]
k = int(np.nanargmax(m))
frame(k); fig.savefig(S.FIG / f"fig_episode_peak_{dates[0][:4]}.png", bbox_inches="tight", dpi=150)
print(out.name, "peak day", dates[k], round(m[k], 2), "valid-day plain AOD range", round(np.nanmin(m), 2), round(np.nanmax(m), 2))
