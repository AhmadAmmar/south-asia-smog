"""Every OpenAQ PM2.5 and NO2 sensor in the study region (60-98 E, 5-37 N), daily means 2019 to yesterday.

    python src/08_openaq_region.py

Ground truth for the gridded PM2.5 model and the street-scale NO2 model (docs/exposure_plan.md). Reference monitors
(isMonitor) and low-cost sensors are both kept, flagged, so they can be used or tested separately. Incremental: a
sensor's series is re-read only from its last stored date minus 3 days. Key from OPENAQ_API_KEY, never stored.
Writes outputs/openaq_region_sensors.csv and outputs/openaq_region_daily.csv (sensor, date, value, coverage).
"""
import importlib.util
from pathlib import Path

import pandas as pd

import smoglib as S

spec = importlib.util.spec_from_file_location("oa", Path(__file__).with_name("06_openaq.py"))
oa = importlib.util.module_from_spec(spec); spec.loader.exec_module(oa)
PARAM = {2: "pm25", 5: "no2"}
BOXES = [(w, s, w + 4, s + 4) for w in range(60, 98, 4) for s in range(5, 37, 4)]   # API bbox limit


def locations():
    rows = []
    for b in BOXES:
        for pid, name in PARAM.items():
            page = 1
            while True:
                res = oa.get("locations", bbox=",".join(map(str, b)), parameters_id=pid, limit=1000, page=page)["results"]
                for l in res:
                    last = (l.get("datetimeLast") or {}).get("utc")
                    if not last or last < "2019-01-01":
                        continue
                    for s in l["sensors"]:
                        if s["parameter"]["name"] == name:
                            rows.append({"sensor": s["id"], "param": name, "location": l["name"], "country": (l.get("country") or {}).get("code"),
                                         "provider": (l.get("provider") or {}).get("name"), "monitor": bool(l.get("isMonitor")),
                                         "lon": l["coordinates"]["longitude"], "lat": l["coordinates"]["latitude"],
                                         "first": ((l.get("datetimeFirst") or {}).get("utc") or "")[:10], "last": last[:10]})
                if len(res) < 1000:
                    break
                page += 1
        print("box", b, len(rows), flush=True)
    return pd.DataFrame(rows).drop_duplicates("sensor")


def series(sensor, start):
    out, page = [], 1
    end = (pd.Timestamp.today() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    while True:
        res = oa.get(f"sensors/{sensor}/days", date_from=start, date_to=end, limit=1000, page=page)["results"]
        out += [{"sensor": sensor, "date": r["period"]["datetimeFrom"]["local"][:10], "value": r["value"],
                 "coverage": (r.get("coverage") or {}).get("percentComplete")} for r in res]
        if len(res) < 1000:
            return out
        page += 1


if __name__ == "__main__":
    sens = locations()
    sens.to_csv(S.OUT / "openaq_region_sensors.csv", index=False)
    print(sens.groupby(["param", "monitor", "country"]).size().to_string(), flush=True)
    f = S.OUT / "openaq_region_daily.csv"
    old = pd.read_csv(f) if f.exists() else pd.DataFrame(columns=["sensor", "date", "value", "coverage"])
    last = old.groupby("sensor").date.max().to_dict()
    new = []
    for i, s in enumerate(sens.itertuples()):
        start = (pd.Timestamp(last[s.sensor]) - pd.Timedelta(days=3)).strftime("%Y-%m-%d") if s.sensor in last else "2019-01-01"
        try:
            new += series(s.sensor, start)
        except Exception as e:
            print("  fail", s.sensor, str(e)[:80], flush=True)
        if i % 25 == 0:
            print(f"{i}/{len(sens)} sensors, {len(new)} new days", flush=True)
            pd.concat([old, pd.DataFrame(new)]).drop_duplicates(["sensor", "date"], keep="last").to_csv(f, index=False)
    pd.concat([old, pd.DataFrame(new)]).drop_duplicates(["sensor", "date"], keep="last").sort_values(["sensor", "date"]).to_csv(f, index=False)
    print("done", len(sens), "sensors")
