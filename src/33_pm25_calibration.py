"""Satellite AOD against ground PM2.5, and a calibrated PM2.5 estimate.

Ground truth: daily PM2.5 from reference monitors (06_openaq.py), city value = median of monitors with >= 75 %
of hours that day (where coverage is reported), values kept between 1 and 1000 ug m-3.

Models (ordinary least squares on logarithms, with a separate intercept per city):
  A  log PM = a_city + b log AOD
  B  A + c log(mixing height) + d log(1 - RH/100)            (the column spread over a shallower, drier layer)
  C  B + e log(wind) + month effects
  D  C + f log(NO2 column): NO2 marks combustion sources that also emit primary particles and precursors
Skill by leave-one-year-out cross-validation: every year is predicted by a model fitted on the other years. RMSE in
ug m-3 after back-transforming with Duan's smearing factor.

The estimate is a statistical model for days with a valid AOD retrieval only; fog and dense smog days are often
missing (flagged as cloud), so it underrepresents the worst days. Labelled "estimated PM2.5" everywhere.

Writes outputs/pm25_ground_daily.csv, outputs/pm25_model_skill.csv, outputs/pm25_estimate_daily.csv;
figures fig_pm25_skill, fig_pm25_scatter, fig_pm25_cycle.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import smoglib as S

plt.rcParams.update({"font.size": 8, "figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False})

g = pd.read_csv(S.OUT / "openaq_daily.csv")
g = g[(g.pm25 > 1) & (g.pm25 < 1000) & ((g.coverage.isna()) | (g.coverage >= 75))]
ground = g.groupby(["city", "date"]).agg(pm25=("pm25", "median"), monitors=("sensor", "nunique")).reset_index()
ground.to_csv(S.OUT / "pm25_ground_daily.csv", index=False)

d = pd.read_csv(S.OUT / "city_daily.csv").merge(pd.read_csv(S.OUT / "city_humidity.csv"), on=["city", "date"], how="left")
d = d.merge(ground, on=["city", "date"], how="left")
d["date"] = pd.to_datetime(d.date)
d["year"], d["month"] = d.date.dt.year, d.date.dt.month
d.loc[d.aod <= 0, "aod"] = np.nan
d["x_aod"] = np.log(d.aod)
d["x_blh"] = np.log(d.boundary_layer_height)
d["x_rh"] = np.log(1 - d.rh.clip(upper=98) / 100)
d["x_wind"] = np.log(d.wind)
d["x_no2"] = np.log(d.no2.where(d.no2 > 1))
d["y"] = np.log(d.pm25)

MODELS = {"A": ["x_aod"], "B": ["x_aod", "x_blh", "x_rh"], "C": ["x_aod", "x_blh", "x_rh", "x_wind", "month"],
          "D": ["x_aod", "x_blh", "x_rh", "x_wind", "month", "x_no2"]}


def design(df, terms, cities):
    """Design matrix: one intercept per city, then month dummies (February to December) or the named
    columns."""
    cols = [np.asarray(df.city == c, float) for c in cities]
    for t in terms:
        if t == "month":
            cols += [np.asarray(df.month == m, float) for m in range(2, 13)]
        else:
            cols.append(df[t].values)
    return np.column_stack(cols)


def fit(df, terms, cities):
    """Least-squares fit of PM2.5 on the design; coefficients and the Duan smearing factor (mean of exp(residual))."""
    X = design(df, terms, cities)
    beta, *_ = np.linalg.lstsq(X, df.y.values, rcond=None)
    resid = df.y.values - X @ beta
    return beta, np.mean(np.exp(resid))       # Duan smearing


rows, preds = [], []
for name, terms in MODELS.items():
    need = [t for t in terms if t != "month"] + ["y"]
    data = d.dropna(subset=need)
    cities = sorted(data.city.unique())
    out = []
    for y in sorted(data.year.unique()):
        tr, te = data[data.year != y], data[data.year == y]
        if len(te) == 0 or len(tr) < 100:
            continue
        b, sm = fit(tr, terms, cities)
        te = te.assign(pred=np.exp(design(te, terms, cities) @ b) * sm, model=name)
        out.append(te)
    p = pd.concat(out)
    preds.append(p)
    for c, q in [("all cities", p)] + list(p.groupby("city")):
        rows.append({"model": name, "city": c, "n": len(q), "r2_log": np.corrcoef(np.log(q.pm25), np.log(q.pred))[0, 1] ** 2,
                     "rmse": float(np.sqrt(np.mean((q.pm25 - q.pred) ** 2))), "bias": float(np.mean(q.pred - q.pm25)),
                     "mean_obs": q.pm25.mean()})
skill = pd.DataFrame(rows)
skill.round(3).to_csv(S.OUT / "pm25_model_skill.csv", index=False)
print(skill.pivot(index="city", columns="model", values="r2_log").round(2).join(
      skill[skill.model == "D"].set_index("city")[["n", "rmse", "mean_obs"]].round(0)).to_string())

# simple correlations: does the surface proxy beat raw AOD?
cor = []
for c, q in d.dropna(subset=["pm25", "aod", "boundary_layer_height"]).groupby("city"):
    cor.append({"city": c, "n": len(q), "rho_aod": spearmanr(q.pm25, q.aod)[0],
                "rho_proxy": spearmanr(q.pm25, q.aod / q.boundary_layer_height)[0],
                "rho_no2": spearmanr(q.pm25, q.no2, nan_policy="omit")[0]})
cor = pd.DataFrame(cor)
cor.round(3).to_csv(S.OUT / "pm25_correlations.csv", index=False)
print(cor.round(2).to_string())

# figures
fig, ax = plt.subplots(figsize=(8, 3.8))
sk = skill[skill.city != "all cities"].pivot(index="city", columns="model", values="r2_log")
sk.plot.bar(ax=ax, rot=0, color=["#bbbbbb", "#E69F00", "#0072B2", "#009E73"], width=0.8)
ax.set_ylabel("R² of log PM2.5, leave-one-year-out"); ax.legend(["A: AOD", "B: + mixing height, humidity", "C: + wind, month", "D: + NO₂ column"], frameon=False, fontsize=7)
ax.set_title("How well satellite AOD predicts ground PM2.5 (reference monitors, OpenAQ)")
fig.savefig(S.FIG / "fig_pm25_skill.png", bbox_inches="tight"); fig.savefig(S.FIG / "fig_pm25_skill.pdf", bbox_inches="tight"); plt.close(fig)

P = pd.concat(preds)
fig, axs = plt.subplots(1, 2, figsize=(10, 4.5), sharex=True, sharey=True)
for ax, m in zip(axs, ("A", "D")):
    q = P[P.model == m]
    ax.hexbin(q.pm25, q.pred, gridsize=60, xscale="log", yscale="log", bins="log", cmap="Greys", mincnt=1)
    ax.plot([3, 800], [3, 800], color="r", lw=0.8)
    s = skill[(skill.model == m) & (skill.city == "all cities")].iloc[0]
    ax.set_title(f"Model {m}: R² (log) {s.r2_log:.2f}, RMSE {s.rmse:.0f} µg m⁻³, n = {s.n}")
    ax.set_xlabel("Ground PM2.5 (µg m⁻³)")
axs[0].set_ylabel("Estimated PM2.5 from satellite (µg m⁻³)")
fig.savefig(S.FIG / "fig_pm25_scatter.png", bbox_inches="tight"); fig.savefig(S.FIG / "fig_pm25_scatter.pdf", bbox_inches="tight"); plt.close(fig)

# estimate for all city-days with inputs, model C fitted on everything
IN = ["x_aod", "x_blh", "x_rh", "x_wind", "x_no2"]
data = d.dropna(subset=IN + ["y"])
cities = sorted(data.city.unique())
b, sm = fit(data, MODELS["D"], cities)
e = d[d.city.isin(cities)].dropna(subset=IN).copy()
e["pm25_est"] = np.exp(design(e, MODELS["D"], cities) @ b) * sm
e[["city", "date", "pm25_est", "pm25"]].to_csv(S.OUT / "pm25_estimate_daily.csv", index=False)
fig, ax = plt.subplots(figsize=(8, 4))
for i, c in enumerate(cities):
    q = e[e.city == c]
    col = plt.cm.tab10(i % 10)
    ax.plot(q.groupby(q.date.dt.month).pm25_est.median(), color=col, lw=1.8, label=f"{c} (estimated)")
    ax.plot(q.groupby(q.date.dt.month).pm25.median(), color=col, lw=0.8, ls="--")
ax.axhline(15, color="k", lw=0.6, ls=":"); ax.text(12.1, 15, "WHO 24 h\nguideline", fontsize=6, va="center")
ax.set_xticks(range(1, 13), list("JFMAMJJASOND")); ax.set_ylabel("Median daily PM2.5 (µg m⁻³)")
ax.set_title("Estimated PM2.5 from satellite (solid) and ground monitors (dashed), days with valid AOD")
ax.legend(fontsize=6.5, frameon=False, ncol=2)
fig.savefig(S.FIG / "fig_pm25_cycle.png", bbox_inches="tight"); fig.savefig(S.FIG / "fig_pm25_cycle.pdf", bbox_inches="tight"); plt.close(fig)
print("coefficients (D, slopes):", dict(zip(["aod", "blh", "rh", "wind", "no2"], np.round(np.r_[b[len(cities):len(cities) + 4], b[-1]], 3))))
