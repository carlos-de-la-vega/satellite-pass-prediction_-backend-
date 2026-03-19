from flask import Flask, jsonify, send_file
from flask_cors import CORS
from skyfield.api import load, wgs84, EarthSatellite
from datetime import datetime
import pandas as pd
import requests

app = Flask(__name__)
CORS(app)

# CACHE GLOBAL
CACHE = []
READY = False

# ---------------- PARAMS ----------------
LAT, LON = 41.2235594, 1.7365296
fromDatetime = "2026-03-19T00:00:00.001Z"
toDatetime = "2026-03-19T06:00:00.001Z"
minElev = 30.0
minDuration = 3.0
# ----------------------------------------

ts = load.timescale()

satellites = {
    "KINEIS-1A": 60084,
    "KINEIS-1B": 60079
}

def fetch_tle(norad_id):
    url = f"https://celestrak.com/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        lines = r.text.strip().splitlines()
        if len(lines) < 3:
            return None
        return lines
    except Exception as e:
        print(f"Error fetching TLE {norad_id}: {e}")
        return None


def compute_passes():
    print("Computando pases...")

    start_dt = datetime.fromisoformat(fromDatetime.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(toDatetime.replace("Z", "+00:00"))

    start = ts.from_datetime(start_dt)
    end = ts.from_datetime(end_dt)
    observer = wgs84.latlon(LAT, LON)

    results = []

    for name, norad in satellites.items():
        tle = fetch_tle(norad)
        if tle is None:
            continue

        try:
            name_line, l1, l2 = tle
            sat = EarthSatellite(l1, l2, name, ts)

            t, events = sat.find_events(observer, start, end, altitude_degrees=minElev)

            for i in range(0, len(events), 3):
                if i + 2 < len(events):
                    if events[i] == 0 and events[i+1] == 1 and events[i+2] == 2:
                        rise_time = t[i]
                        culm_time = t[i+1]
                        set_time = t[i+2]

                        alt, az, _ = (sat - observer).at(culm_time).altaz()
                        elevation_deg = alt.degrees

                        duration_min = (
                            set_time.utc_datetime() - rise_time.utc_datetime()
                        ).total_seconds() / 60

                        if duration_min >= minDuration:
                            results.append({
                                "Satellite": name,
                                "Rise": rise_time.utc_strftime('%Y-%m-%d %H:%M:%S'),
                                "Culmination": culm_time.utc_strftime('%Y-%m-%d %H:%M:%S'),
                                "Set": set_time.utc_strftime('%Y-%m-%d %H:%M:%S'),
                                "Max Elevation (deg)": round(elevation_deg, 2),
                                "Duration (min)": round(duration_min, 1)
                            })

        except Exception as e:
            print(f"Error with {name}: {e}")

    df = pd.DataFrame(results)
    df.to_csv("satellite_passes_detailed.csv", index=False)

    print("Cálculo terminado")
    return results


# CALCULAR AL ARRANCAR
print("Inicializando servidor...")
try:
    CACHE = compute_passes()
    READY = True
    print("Servidor listo")
except Exception as e:
    print("Error inicial:", e)


# Endpoint JSON
@app.route("/passes")
def get_passes():
    if not READY:
        return jsonify({"status": "loading"}), 503
    return jsonify(CACHE)


# Endpoint CSV
@app.route("/download")
def download_csv():
    if not READY:
        return "Data not ready", 503
    return send_file("satellite_passes_detailed.csv", as_attachment=True)


# Ruta base
@app.route("/")
def home():
    return "API funcionando 🚀"


if __name__ == "__main__":
    app.run()
