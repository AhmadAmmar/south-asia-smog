"""Surface NO2 by district from Sentinel-5P, calibrated on reference monitors, and the share of children's asthma and of
deaths attributable to it, 2019 to the last full year.

    python src/51_no2_asthma.py [--years 2019-2025]

1. Annual mean NO2 at every OpenAQ reference monitor (outputs/openaq_region_*; days with coverage, >= 180 days a year).
2. Predictors at each monitor: TROPOMI tropospheric NO2 column (annual mean, OFFL L3, cloud-screened by the L3
   product) at 1 km, and log population density (GPWv4.11, 2020).
3. Calibration: surface NO2 (ug/m3) = a + b x column + c x log(density), ordinary least squares, checked by
   leave-one-city-out cross-validation (R2, RMSE) so the map is not trusted beyond what the monitors support.
4. District population-weighted surface NO2 (Earth Engine, 1 km) and:
   - paediatric asthma incidence attributable fraction: RR 1.26 (1.10-1.37) per 10 ppb (Khreis et al. 2017, as used by
     Achakulwisut et al. 2019), 1 ppb = 1.88 ug/m3, counterfactual 2 ppb (lowest exposure in the cohorts, a
     sensitivity choice);
   - all-cause mortality: RR 1.02 (1.01-1.04) per 10 ug/m3 (Huangfu and Atkinson 2020), counterfactual 10 ug/m3
     (WHO 2021 annual guideline); attributable deaths = WPP deaths x AF. NO2 and PM2.5 deaths overlap and must not
     be added together.
Writes outputs/no2_monitor_annual.csv, no2_calibration.csv, no2_district_year.csv, figures/no2_*.png.
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
MOL_TO_UGM3 = None  # surface concentrations come from monitors in ug/m3; the column is only a predictor


def monitors(years):
    s = pd.read_csv(O / "openaq_region_sensors.csv")
    s = s[(s.param.str.lower() == "no2") & (s.monitor == True)]
    d = pd.read_csv(O / "openaq_region_daily.csv")
    d = d[d.sensor.isin(s.sensor)]
    d["year"] = d.date.str[:4].astype(int)
    a = d[d.year.isin(years)].groupby(["sensor", "year"]).agg(no2=("value", "mean"), days=("value", "size")).reset_index()
    a = a[a.days >= 180].merge(s[["sensor", "location", "country", "lon", "lat"]], on="sensor")
    # OpenAQ NO2 is reported in ppb by some providers and ug/m3 by others; CPCB and Pakistan EPAs report ug/m3.
    # Values in ppb are flagged by the sensor unit in the sensors table where present.
    if "units" in s.columns:
        u = s.set_index("sensor").units
        a.loc[a.sensor.map(u).str.contains("ppb", na=False), "no2"] *= 1.88
    a.to_csv(O / "no2_monitor_annual.csv", index=False)
    print("monitor-years", len(a), "monitors", a.sensor.nunique(), "countries", a.country.value_counts().to_dict(), flush=True)
    return a


def predictors(a, years):
    import ee
    ee.Initialize(project="ee-ahmadammargeo")
    dens = ee.ImageCollection("CIESIN/GPWv411/GPW_Population_Density").filter(ee.Filter.calendarRange(2020, 2020, "year")).first().max(1).log10().rename("logdens")
    out = []
    for y in years:
        col = (ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2").filterDate(f"{y}-01-01", f"{y + 1}-01-01")
               .select("tropospheric_NO2_column_number_density").mean().multiply(1e6).rename("col"))     # umol/m2
        sub = a[a.year == y]
        if sub.empty:
            continue
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([r.lon, r.lat]), {"sensor": int(r.sensor)}) for r in sub.itertuples()])
        got = ee.Image.cat(col, dens).reduceRegions(fc, ee.Reducer.mean(), 1000).getInfo()
        p = pd.DataFrame([f["properties"] for f in got["features"]]); p["year"] = y
        out.append(p)
    return a.merge(pd.concat(out), on=["sensor", "year"])


def calibrate(m):
    m = m.dropna(subset=["col", "logdens", "no2"])
    X = np.column_stack([np.ones(len(m)), m.col, m.logdens]); yv = m.no2.values
    coef = np.linalg.lstsq(X, yv, rcond=None)[0]
    pred = np.zeros(len(m))
    for city in m.location.str.split(",").str[-1].str.strip().unique():
        test = (m.location.str.split(",").str[-1].str.strip() == city).values
        if test.all():
            continue
        c = np.linalg.lstsq(X[~test], yv[~test], rcond=None)[0]; pred[test] = X[test] @ c
    r2 = 1 - np.sum((yv - pred) ** 2) / np.sum((yv - yv.mean()) ** 2); rmse = np.sqrt(np.mean((yv - pred) ** 2))
    cal = pd.DataFrame([{"a": coef[0], "b_per_umolm2": coef[1], "c_logdens": coef[2], "n": len(m), "cv_r2_leave_city_out": r2, "cv_rmse_ugm3": rmse}])
    cal.round(4).to_csv(O / "no2_calibration.csv", index=False); print(cal.round(3).to_string(index=False), flush=True)
    return coef


def districts(coef, years):
    import ee
    ee.Initialize(project="ee-ahmadammargeo")
    adm = ee.FeatureCollection("WM/geoLab/geoBoundaries/600/ADM2").filter(ee.Filter.inList("shapeGroup", ISO))
    dens = ee.ImageCollection("CIESIN/GPWv411/GPW_Population_Density").filter(ee.Filter.calendarRange(2020, 2020, "year")).first().max(1).log10()
    pop = ee.ImageCollection("CIESIN/GPWv411/GPW_Population_Count").filter(ee.Filter.calendarRange(2020, 2020, "year")).first().rename("pop")
    rows = []
    for y in years:
        col = (ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2").filterDate(f"{y}-01-01", f"{y + 1}-01-01")
               .select("tropospheric_NO2_column_number_density").mean().multiply(1e6))
        no2 = col.multiply(coef[1]).add(dens.multiply(coef[2])).add(coef[0]).max(0).rename("no2")
        img = ee.Image.cat(no2.multiply(pop).rename("no2_pop"), pop)
        got = img.reduceRegions(adm, ee.Reducer.sum(), 1000, tileScale=8).select(["shapeGroup", "shapeName", "shapeID", "no2_pop", "pop"], retainGeometry=False).getInfo()
        for f in got["features"]:
            p = f["properties"]; p["year"] = y; rows.append(p)
        print(y, "districts", len(got["features"]), flush=True)
    d = pd.DataFrame(rows)
    d["no2_popw"] = d.no2_pop / d["pop"]
    wpp = pd.read_csv(R / "data/raw/wpp/WPP2024_Demographic_Indicators_Medium.csv.gz", low_memory=False)
    wpp = wpp[wpp.ISO3_code.isin(ISO)][["ISO3_code", "Time", "TPopulation1July", "Deaths"]].rename(columns={"ISO3_code": "shapeGroup", "Time": "year"})
    d = d.merge(wpp, on=["shapeGroup", "year"], how="left")
    share = d["pop"] / d.groupby(["shapeGroup", "year"])["pop"].transform("sum")
    d["population"] = share * d.TPopulation1July * 1000; d["deaths_all"] = share * d.Deaths * 1000
    ppb = d.no2_popw / 1.88
    for k, rr in (("", 1.26), ("_lo", 1.10), ("_hi", 1.37)):
        d[f"af_child_asthma{k}"] = 1 - rr ** (-np.maximum(0, ppb - 2) / 10)
    for k, rr in (("", 1.02), ("_lo", 1.01), ("_hi", 1.04)):
        d[f"deaths_no2{k}"] = d.deaths_all * (1 - rr ** (-np.maximum(0, d.no2_popw - 10) / 10))
    d.round(4).to_csv(O / "no2_district_year.csv", index=False)
    c = d.groupby(["shapeGroup", "year"]).apply(lambda x: pd.Series({
        "no2_popw": np.average(x.no2_popw, weights=x.population), "af_child_asthma": np.average(x.af_child_asthma, weights=x.population),
        "deaths_no2_k": x.deaths_no2.sum() / 1e3, "deaths_no2_lo_k": x.deaths_no2_lo.sum() / 1e3, "deaths_no2_hi_k": x.deaths_no2_hi.sum() / 1e3})).reset_index()
    c.round(3).to_csv(O / "no2_country_year.csv", index=False); print(c[c.year == c.year.max()].round(3).to_string(index=False))
    return d


def figures(d):
    import geopandas as gpd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    g = gpd.read_file(R / "data/processed/adm2_south_asia.gpkg")
    y = d.year.max(); m = g.merge(d[d.year == y], on="shapeID")
    fig, axs = plt.subplots(1, 2, figsize=(15, 7.5))
    m.plot(column="no2_popw", ax=axs[0], cmap="YlOrBr", vmin=0, vmax=60, lw=0.05, edgecolor="0.6", legend=True, legend_kwds={"shrink": 0.6, "label": "surface NO2, population-weighted (ug/m3)"})
    m.plot(column="af_child_asthma", ax=axs[1], cmap="PuRd", vmin=0, vmax=0.5, lw=0.05, edgecolor="0.6", legend=True, legend_kwds={"shrink": 0.6, "label": "share of new childhood asthma attributable to NO2"})
    for ax in axs:
        ax.set_axis_off()
    fig.suptitle(f"NO2 and childhood asthma by district, {y}", fontsize=13)
    fig.text(0.01, 0.01, "Surface NO2: Sentinel-5P TROPOMI column calibrated on OpenAQ reference monitors (see no2_calibration.csv for cross-validated skill). "
             "Asthma: RR 1.26 per 10 ppb (Khreis et al. 2017), counterfactual 2 ppb.", fontsize=7.5, color="0.35")
    fig.savefig(F / f"no2_asthma_districts_{y}.png", dpi=140, bbox_inches="tight"); plt.close(fig)


def main(years):
    a = monitors(years)
    m = predictors(a, years)
    coef = calibrate(m)
    d = districts(coef, years)
    figures(d)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--years", default="2019-2025")
    a, b = map(int, ap.parse_args().years.split("-"))
    main(list(range(a, b + 1)))
