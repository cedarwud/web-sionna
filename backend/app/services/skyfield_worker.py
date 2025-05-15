# backend/app/services/skyfield_worker.py
from skyfield.api import EarthSatellite, load, wgs84
from fastapi.encoders import jsonable_encoder
import json, os, time, sys

ts = load.timescale()
l1 = os.getenv("SAT_TLE_LINE1")
l2 = os.getenv("SAT_TLE_LINE2")
sat = EarthSatellite(l1, l2, "LEO", ts)

while True:
    t = ts.now()
    geo = sat.at(t)
    sub = wgs84.subpoint(geo)
    data = {
        "ts": t.utc_strftime(),
        "sat": dict(
            lat=sub.latitude.degrees, lon=sub.longitude.degrees, alt_km=sub.elevation.km
        ),
    }
    print(json.dumps(jsonable_encoder(data)), flush=True)
    time.sleep(1)
