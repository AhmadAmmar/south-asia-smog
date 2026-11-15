"""Candidate point sources inside the region, for attributing hotspots:

  power plants  WRI Global Power Plant Database v1.3 (Earth Engine WRI/GPPD/power_plants): fuel, capacity (MW)
  cities        Natural Earth populated places (10 m), with population estimates

Writes outputs/power_plants.csv and outputs/cities_ne.csv.
"""
import cartopy.io.shapereader as shp
import ee
import pandas as pd

import smoglib as S

S.init()
reg = ee.Geometry.Rectangle([S.WEST, S.SOUTH, S.EAST, S.NORTH], None, False)
fc = ee.FeatureCollection("WRI/GPPD/power_plants").filterBounds(reg)
info = fc.getInfo()["features"]
rows = [{"name": f["properties"].get("name"), "fuel": f["properties"].get("fuel1"), "mw": f["properties"].get("capacitymw"),
         "country": f["properties"].get("country_lg"), "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]}
        for f in info]
pp = pd.DataFrame(rows)
pp.to_csv(S.OUT / "power_plants.csv", index=False)
print(len(pp), "plants;", pp.groupby("fuel").mw.sum().round().sort_values(ascending=False).head(6).to_dict())

r = shp.Reader(shp.natural_earth("10m", "cultural", "populated_places"))
cities = pd.DataFrame([{"name": x.attributes["NAME"], "pop": x.attributes["POP_MAX"], "lon": x.geometry.x, "lat": x.geometry.y}
                       for x in r.records()])
cities = cities[cities.lon.between(S.WEST, S.EAST) & cities.lat.between(S.SOUTH, S.NORTH)]
cities.to_csv(S.OUT / "cities_ne.csv", index=False)
print(len(cities), "places")
