"""Ground PM2.5 from OpenAQ (API v3): daily means at monitors within 25 km of each city, 2019 to now.

The API key is read from the OPENAQ_API_KEY environment variable (Windows user variable as a fallback); it is never
written to any file.

Sensor choice: reference monitors only (OpenAQ isMonitor = true: government networks, US embassy StateAir), up to 15
per city, longest record first. Low-cost sensors (AirGradient, PurpleAir, Clarity and others) are kept out of the
calibration because they read high in humid winter air without correction. Cities with no reference monitor are
reported as such.

Writes outputs/openaq_sensors.csv (one row per sensor used) and outputs/openaq_daily.csv
(city, sensor, date, pm25 in ug m-3, coverage %).
"""
import os
import time

import pandas as pd
import requests

import smoglib as S

API = "https://api.openaq.org/v3"


def key():
    k = os.environ.get("OPENAQ_API_KEY")
    if not k:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
            k = winreg.QueryValueEx(h, "OPENAQ_API_KEY")[0]
    return k


SES = requests.Session()
SES.headers["X-API-Key"] = key()


def get(path, **params):
    for k in range(6):
        r = SES.get(f"{API}/{path}", params=params, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(10 * (k + 1)); continue
        r.raise_for_status()
        time.sleep(1.1)                       # free tier: 60 requests a minute
        return r.json()
    r.raise_for_status()


def sensors(city, lon, lat):
    locs = get("locations", coordinates=f"{lat},{lon}", radius=25000, limit=1000, parameters_id=2)["results"]
    rows = []
    for l in locs:
        for s in l["sensors"]:
            if s["parameter"]["name"] != "pm25":
                continue
            first, last = (l.get("datetimeFirst") or {}).get("utc"), (l.get("datetimeLast") or {}).get("utc")
            if not first or not last or last < "2019-01-01":
                continue
            rows.append({"city": city, "sensor": s["id"], "location": l["name"], "provider": (l.get("provider") or {}).get("name"),
                         "monitor": bool(l.get("isMonitor")), "lon": l["coordinates"]["longitude"], "lat": l["coordinates"]["latitude"],
                         "first": first[:10], "last": last[:10],
                         "days_span": (pd.Timestamp(last[:10]) - pd.Timestamp(max(first[:10], "2019-01-01"))).days})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df[df.monitor].sort_values("days_span", ascending=False).head(15)


def daily(sensor):
    out, page = [], 1
    while True:
        j = get(f"sensors/{sensor}/days", date_from="2019-01-01", date_to="2026-11-01", limit=1000, page=page)
        res = j["results"]
        out += [{"date": r["period"]["datetimeFrom"]["local"][:10], "pm25": r["value"],
                 "coverage": (r.get("coverage") or {}).get("percentComplete")} for r in res]
        if len(res) < 1000:
            return out
        page += 1


if __name__ == "__main__":
    sens = pd.concat([sensors(c, *xy) for c, xy in S.CITIES.items()], ignore_index=True)
    sens.to_csv(S.OUT / "openaq_sensors.csv", index=False)
    print(sens.groupby("city").agg(n=("sensor", "size"), providers=("provider", lambda x: ", ".join(sorted(set(map(str, x)))))).to_string(), flush=True)
    rows = []
    for _, s in sens.iterrows():
        d = daily(s.sensor)
        rows += [{"city": s.city, "sensor": s.sensor, **r} for r in d]
        print(s.city, s.location[:35], len(d), "days", flush=True)
    pd.DataFrame(rows).to_csv(S.OUT / "openaq_daily.csv", index=False)
