"""Cigarette equivalent and life expectancy lost for Lahore and Delhi after the satellite record ends (2022).

    python src/52_city_update.py

The satellite PM2.5 (step 50) stops in 2022. Later years scale the 2022 district value by the change seen at ground
monitors (outputs/openaq_region_daily.csv), always comparing like with like:
- Delhi: CPCB/AirNow reference network. 2025 / 2022 full-year ratio; 2026 / 2022 over 1 Jan - 14 Nov (data to date),
  so 2026 is provisional and misses the worst weeks (mid-Nov to Dec).
- Lahore: the US consulate reference monitor (StateAir) ends Feb 2025. Chain: StateAir 2024/2022 full year, then the
  median ratio of the same low-cost sensors (Clarity, AirGradient, Hawanama; >= 150 days in both years) over 1 Jan -
  14 Nov: 2025/2024 (only 1 sensor qualifies: weak) and 2026/2025 (7 sensors). Low-cost sensors are uncalibrated but
  a ratio from the same sensor cancels most of its bias.
Same formulas as step 50: cigarettes/day = PM2.5 / 22; life years lost = 0.098 x (PM2.5 - 5).
Writes outputs/city_update_2025_2026.csv.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[1]
BOX = {"Lahore": (74.1, 74.6, 31.3, 31.7, "Lahore"), "Delhi": (76.8, 77.4, 28.4, 28.9, "New Delhi")}


def load():
    """Daily PM2.5 of the regional sensors (values 0-1000) with sensor details."""
    s = pd.read_csv(R / "outputs/openaq_region_sensors.csv"); s = s[s.param == "pm25"]
    d = pd.read_csv(R / "outputs/openaq_region_daily.csv"); d = d[d.sensor.isin(s.sensor) & (d.value > 0) & (d.value < 1000)]
    d = d.merge(s[["sensor", "monitor", "provider", "lon", "lat"]], on="sensor")
    d["year"] = d.date.str[:4].astype(int); d["md"] = d.date.str[5:]
    return d


def citymean(x, y, window=False):
    """Mean PM2.5 of a year (optionally only to 14 November)."""
    z = x[x.year == y]
    if window:
        z = z[z.md <= "11-14"]
    return z.groupby("date").value.mean().mean()


def same_sensor(x, a, b):
    """Year-on-year change at sensors with 150 or more days in both years, to 14 November."""
    z = x[x.year.isin([a, b]) & (x.md <= "11-14")]
    g = z.groupby(["sensor", "year"]).value.agg(["mean", "size"]).unstack()
    g = g.dropna(); g = g[(g["size"][a] >= 150) & (g["size"][b] >= 150)]
    return float((g["mean"][b] / g["mean"][a]).median()), len(g)


def main():
    """City update: this season against last, at the same sensors, with district exposure."""
    d = load()
    ex = pd.read_csv(R / "outputs/exposure_district_year.csv")
    rows = []
    for city, (w, e, s_, n, dist) in BOX.items():
        x = d[d.lon.between(w, e) & d.lat.between(s_, n)]
        ref = x[x.monitor == True]; low = x[x.monitor != True]
        base = float(ex[(ex.shapeName == dist) & (ex.year == 2022)].pm25_popw.iloc[0])
        rows.append((city, 2022, base, "satellite (van Donkelaar V6.GL.02)"))
        if city == "Delhi":
            r25 = citymean(ref, 2025) / citymean(ref, 2022)
            r26 = citymean(ref, 2026, True) / citymean(ref, 2022, True)
            rows += [(city, 2025, base * r25, f"x reference-network ratio {r25:.3f}"),
                     (city, 2026, base * r26, f"x reference-network ratio {r26:.3f} (Jan-14 Nov, provisional)")]
        else:
            r24 = citymean(ref, 2024) / citymean(ref, 2022)
            r2425, n1 = same_sensor(low, 2024, 2025); r2526, n2 = same_sensor(low, 2025, 2026)
            p25 = base * r24 * r2425; p26 = p25 * r2526
            rows += [(city, 2025, p25, f"x StateAir 2024/2022 {r24:.3f} x same-sensor 2025/2024 {r2425:.3f} (n={n1}, weak)"),
                     (city, 2026, p26, f"x same-sensor 2026/2025 {r2526:.3f} (n={n2}, Jan-14 Nov, provisional)")]
    o = pd.DataFrame(rows, columns=["city", "year", "pm25", "method"])
    o["cigarettes_per_day"] = o.pm25 / 22
    o["life_years_lost"] = 0.098 * np.maximum(0, o.pm25 - 5)
    o.round(2).to_csv(R / "outputs/city_update_2025_2026.csv", index=False)
    print(o.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
