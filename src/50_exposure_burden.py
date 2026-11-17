"""Who breathes what, and what it costs in health: PM2.5 exposure, cigarette equivalent, life expectancy loss and
attributable deaths by district across South Asia, every year 1998-2022.

    python src/50_exposure_burden.py [--years 1998-2022]

Data
- PM2.5: van Donkelaar et al. V6.GL.02 annual surface PM2.5 (satellite AOD + GEOS-Chem + ground monitors), 0.01 deg
  (~1 km), 1998-2022 (Earth Engine projects/sat-io/open-datasets/GLOBAL-SATELLITE-PM25/ANNUAL).
- People: CIESIN GPWv4.11 population counts, 30 arc-sec (~1 km), 2000-2020 five-yearly, interpolated linearly
  between epochs and held at the nearest epoch outside 2000-2020; scaled to UN WPP 2024 national totals each year.
- Districts: geoBoundaries ADM2 (v6) for Afghanistan, Pakistan, India, Nepal, Bhutan, Bangladesh, Sri Lanka.
- Deaths: UN World Population Prospects 2024 national deaths per year (all causes, all ages), spread by population.
Calculations per district and year
- population-weighted mean PM2.5; share of people above WHO 2021 guideline (5), interim targets (15, 25, 35) and
  the national annual standards (Pakistan 15 in Punjab EQS / NEQS 15; India NAAQS 40).
- cigarette equivalent per day = PM2.5 / 22 (Berkeley Earth, Muller and Muller 2015: 22 ug/m3 for a day ~ one
  cigarette, matched on mortality; a communication device, not a dose: compared with inhaled dose in step 51).
- life expectancy lost = 0.098 years per ug/m3 above 5 (AQLI, from Ebenstein et al. 2017, 0.98 y per 10 ug/m3).
- attributable fraction, log-linear WHO risks (Chen and Hoek 2020, per 10 ug/m3 above a counterfactual of 5):
  all-cause 1.08 (1.06-1.09); circulatory 1.11; IHD 1.16; stroke 1.11; respiratory 1.10; COPD 1.11; ALRI 1.16;
  lung cancer 1.12. Log-linear extrapolation to 60-100 ug/m3 is beyond the cohorts' range and likely overstates
  risk at the top; flagged as an upper bound until the GEMM / GBD MR-BRT curves are added.
- attributable deaths (all causes) = deaths x AF, with a 95 % range from the risk ratio CI. Cause-specific deaths
  need cause-specific baseline rates (GBD), not yet included: cause-specific AFs are reported.
Writes outputs/exposure_district_year.csv, outputs/exposure_country_year.csv, figures/exposure_*.png.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[1]
O, F = R / "outputs", R / "figures"
ISO = ["AFG", "PAK", "IND", "NPL", "BTN", "BGD", "LKA"]
RR = {"all_cause": (1.08, 1.06, 1.09), "circulatory": (1.11, 1.09, 1.14), "ihd": (1.16, 1.10, 1.21), "stroke": (1.11, 1.04, 1.18),
      "respiratory": (1.10, 1.03, 1.18), "copd": (1.11, 1.05, 1.17), "alri": (1.16, 1.01, 1.34), "lung_cancer": (1.12, 1.07, 1.16)}
CF = 5.0


def district_stats(years):
    import ee
    ee.Initialize(project="ee-ahmadammargeo")
    adm = ee.FeatureCollection("WM/geoLab/geoBoundaries/600/ADM2").filter(ee.Filter.inList("shapeGroup", ISO))
    pmcol = ee.ImageCollection("projects/sat-io/open-datasets/GLOBAL-SATELLITE-PM25/ANNUAL")
    gpw = ee.ImageCollection("CIESIN/GPWv411/GPW_Population_Count")
    epochs = [2000, 2005, 2010, 2015, 2020]
    rows = []
    for y in years:
        pm = pmcol.filter(ee.Filter.stringContains("system:index", f"_{y}01-{y}12")).first().select(0).rename("pm")
        a = max([e for e in epochs if e <= y], default=2000); b = min([e for e in epochs if e >= y], default=2020)
        pa = gpw.filter(ee.Filter.calendarRange(a, a, "year")).first(); pb = gpw.filter(ee.Filter.calendarRange(b, b, "year")).first()
        w = 0 if a == b else (y - a) / (b - a)
        pop = pa.multiply(1 - w).add(pb.multiply(w)).rename("pop")
        img = ee.Image.cat(pm.multiply(pop).rename("pm_pop"), pop,
                           *[pop.updateMask(pm.gt(t)).unmask(0).rename(f"pop_gt{t}") for t in (5, 15, 25, 35, 40, 75)])
        fc = img.reduceRegions(adm, ee.Reducer.sum(), scale=1000, tileScale=8)
        got = fc.select(["shapeGroup", "shapeName", "shapeID", "pm_pop", "pop"] + [f"pop_gt{t}" for t in (5, 15, 25, 35, 40, 75)],
                        retainGeometry=False).getInfo()
        for f in got["features"]:
            p = f["properties"]; p["year"] = y; rows.append(p)
        print(y, len(got["features"]), "districts", flush=True)
    return pd.DataFrame(rows)


def burden(d):
    wpp = pd.read_csv(R / "data/raw/wpp/WPP2024_Demographic_Indicators_Medium.csv.gz", low_memory=False)
    wpp = wpp[wpp.ISO3_code.isin(ISO)][["ISO3_code", "Time", "TPopulation1July", "Deaths"]]
    wpp.columns = ["shapeGroup", "year", "wpp_pop_k", "wpp_deaths_k"]
    d = d.merge(wpp, on=["shapeGroup", "year"], how="left")
    scale = d.groupby(["shapeGroup", "year"])["pop"].transform("sum")
    d["population"] = d["pop"] / scale * d.wpp_pop_k * 1000                        # GPW pattern, WPP totals
    d["deaths_all"] = d["pop"] / scale * d.wpp_deaths_k * 1000
    d["pm25_popw"] = d.pm_pop / d["pop"]
    for t in (5, 15, 25, 35, 40, 75):
        d[f"share_above_{t}"] = d[f"pop_gt{t}"] / d["pop"]
    d["cigarettes_per_day"] = d.pm25_popw / 22
    d["life_years_lost"] = 0.098 * np.maximum(0, d.pm25_popw - CF)
    x = np.maximum(0, d.pm25_popw - CF) / 10
    for k, (rr, lo, hi) in RR.items():
        d[f"af_{k}"] = 1 - rr ** (-x)
    d["deaths_attrib"] = d.deaths_all * d.af_all_cause
    d["deaths_attrib_lo"] = d.deaths_all * (1 - RR["all_cause"][1] ** (-x))
    d["deaths_attrib_hi"] = d.deaths_all * (1 - RR["all_cause"][2] ** (-x))
    d["deaths_attrib_per_100k"] = d.deaths_attrib / d.population * 1e5
    return d.drop(columns=["pm_pop", "pop"] + [f"pop_gt{t}" for t in (5, 15, 25, 35, 40, 75)])


def summaries(d):
    g = d.groupby(["shapeGroup", "year"])
    c = g.apply(lambda x: pd.Series({"population_m": x.population.sum() / 1e6,
                                     "pm25_popw": np.average(x.pm25_popw, weights=x.population),
                                     "share_above_5": np.average(x.share_above_5, weights=x.population),
                                     "share_above_35": np.average(x.share_above_35, weights=x.population),
                                     "cigarettes_per_day": np.average(x.cigarettes_per_day, weights=x.population),
                                     "life_years_lost": np.average(x.life_years_lost, weights=x.population),
                                     "deaths_attrib_k": x.deaths_attrib.sum() / 1e3,
                                     "deaths_attrib_lo_k": x.deaths_attrib_lo.sum() / 1e3, "deaths_attrib_hi_k": x.deaths_attrib_hi.sum() / 1e3}))
    return c.reset_index().round(3)


def figures(d, c):
    import geopandas as gpd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import ee
    ee.Initialize(project="ee-ahmadammargeo")
    shp = R / "data/processed/adm2_south_asia.gpkg"
    if not shp.exists():
        fc = ee.FeatureCollection("WM/geoLab/geoBoundaries/600/ADM2").filter(ee.Filter.inList("shapeGroup", ISO)).map(lambda f: f.simplify(500))
        g = gpd.GeoDataFrame.from_features(fc.getInfo()["features"], crs=4326); shp.parent.mkdir(exist_ok=True, parents=True); g.to_file(shp)
    g = gpd.read_file(shp)
    y = d.year.max()
    m = g.merge(d[d.year == y], on="shapeID")
    panels = [("pm25_popw", "PM2.5, population-weighted (ug/m3)", "magma_r", (0, 110)),
              ("cigarettes_per_day", "Cigarette equivalent per day (PM2.5 / 22)", "Reds", (0, 5)),
              ("life_years_lost", "Life expectancy lost (years, AQLI)", "Purples", (0, 10)),
              ("deaths_attrib_per_100k", "Deaths attributable per 100,000 (all causes, upper bound)", "OrRd", (0, 400))]
    fig, axs = plt.subplots(2, 2, figsize=(14, 13))
    for ax, (col, lab, cm, lim) in zip(axs.flat, panels):
        m.plot(column=col, ax=ax, cmap=cm, vmin=lim[0], vmax=lim[1], linewidth=0.05, edgecolor="0.6",
               legend=True, legend_kwds={"shrink": 0.6, "label": lab})
        ax.set_axis_off(); ax.set_title(lab, fontsize=11)
    fig.suptitle(f"Air pollution and health by district, South Asia, {y}", fontsize=14)
    fig.text(0.01, 0.01, "PM2.5: van Donkelaar et al. V6.GL.02. Population: GPWv4.11 scaled to UN WPP 2024. Districts: geoBoundaries ADM2. "
             "Risks: WHO review (Chen and Hoek 2020), log-linear above 5 ug/m3. Life expectancy: AQLI 0.98 y per 10 ug/m3. "
             "Cigarettes: Berkeley Earth 22 ug/m3 = 1/day.", fontsize=7.5, color="0.35", wrap=True)
    fig.savefig(F / f"exposure_districts_{y}.png", dpi=140, bbox_inches="tight"); plt.close(fig)
    fig, axs = plt.subplots(1, 3, figsize=(16, 4.2))
    for iso, x in c.groupby("shapeGroup"):
        axs[0].plot(x.year, x.pm25_popw, label=iso); axs[1].plot(x.year, x.life_years_lost, label=iso)
        axs[2].plot(x.year, x.deaths_attrib_k, label=iso); axs[2].fill_between(x.year, x.deaths_attrib_lo_k, x.deaths_attrib_hi_k, alpha=0.15)
    for ax, t in zip(axs, ("PM2.5 population-weighted (ug/m3)", "life expectancy lost (years)", "attributable deaths (thousands, all causes)")):
        ax.set_title(t, fontsize=10); ax.spines[["top", "right"]].set_visible(False)
    axs[0].axhline(5, color="0.5", ls=":", lw=0.8); axs[0].legend(fontsize=8, ncol=2)
    fig.savefig(F / "exposure_country_trends.png", dpi=140, bbox_inches="tight"); plt.close(fig)


def main(years):
    raw = O / "exposure_district_raw.csv"
    have = pd.read_csv(raw) if raw.exists() else pd.DataFrame()
    todo = [y for y in years if have.empty or y not in set(have.year)]
    if todo:
        new = district_stats(todo); have = pd.concat([have, new]); have.to_csv(raw, index=False)
    d = burden(have[have.year.isin(years)].copy())
    d.round(4).to_csv(O / "exposure_district_year.csv", index=False)
    c = summaries(d); c.to_csv(O / "exposure_country_year.csv", index=False)
    print(c[c.year.isin([1998, 2010, 2022])].to_string(index=False))
    figures(d, c)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--years", default="1998-2022")
    a, b = map(int, ap.parse_args().years.split("-"))
    main(list(range(a, b + 1)))
