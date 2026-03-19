from flask import Flask, jsonify, send_file
from flask_cors import CORS
from skyfield.api import load, wgs84, EarthSatellite, utc
from datetime import datetime, timedelta
import pandas as pd
import requests

app = Flask(__name__)
CORS(app)

# ---------------- PARAMS ----------------
LAT, LON = 41.2235594, 1.7365296
fromDatetime = "2026-03-19T00:00:00.001Z"
toDatetime = "2026-03-19T23:00:00.001Z"
minElev = 30.0
minDuration = 3.0
# ----------------------------------------

ts = load.timescale()

satellites = {
    "KINEIS-1A": 60084,
    "KINEIS-1B": 60079,
    # ... (igual que tu lista)
    "Oceansat-3": 54361
}

def fetch_tle(norad_id):
    url = f"https://celestrak.com/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"
    r = requests.get(url)
    r.raise_for_status()
    return r.text.strip().splitlines()

def compute_passes():
    start_dt = datetime.fromisoformat(fromDatetime.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(toDatetime.replace("Z", "+00:00")) + timedelta(days=1)

    start = ts.from_datetime(start_dt)
    end = ts.from_datetime(end_dt)
    observer = wgs84.latlon(LAT, LON)

    results = []

    for name, norad in satellites.items():
        try:
            name_line, l1, l2 = fetch_tle(norad)
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

                        duration_min = (set_time.utc_datetime() - rise_time.utc_datetime()).total_seconds() / 60

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

    return results


# 🔹 Endpoint JSON (para HTML)
@app.route("/passes")
def get_passes():
    data = compute_passes()
    return jsonify(data)


# 🔹 Endpoint CSV descarga
@app.route("/download")
def download_csv():
    compute_passes()
    return send_file("satellite_passes_detailed.csv", as_attachment=True)


if __name__ == "__main__":
    app.run()