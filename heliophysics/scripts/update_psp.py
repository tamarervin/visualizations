"""Publish hourly Parker Solar Probe positions from JPL Horizons for MkDocs."""

import csv
from datetime import UTC, datetime, timedelta
import json
import math
from pathlib import Path
import shutil
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "parker" / "psp-orbit.json"
CACHE = ROOT / ".psp-cache" / OUTPUT.name
HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
JULIAN_DATE_UNIX_EPOCH = 2440587.5
SECONDS_PER_DAY = 86400
STEP_SECONDS = 3600


def fetch_orbit(start, stop):
    """Return Sun-centered geometric XYZ vectors in km on a UTC hourly grid."""
    params = {
        "format": "json",
        "COMMAND": "'-96'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'VECTORS'",
        "CENTER": "'500@10'",
        "REF_SYSTEM": "'ICRF'",
        "REF_PLANE": "'ECLIPTIC'",
        "VEC_CORR": "'NONE'",
        "OUT_UNITS": "'KM-S'",
        "TIME_TYPE": "'UT'",
        "VEC_TABLE": "'1'",
        "CSV_FORMAT": "'YES'",
        "START_TIME": start.strftime("'%Y-%m-%d %H:%M'"),
        "STOP_TIME": stop.strftime("'%Y-%m-%d %H:%M'"),
        "STEP_SIZE": "'1 h'",
    }
    request = Request(
        f"{HORIZONS_URL}?{urlencode(params)}",
        headers={"User-Agent": "PSP-Orbit-Tracker/1.0 (+https://github.com/tamarervin/visualizations)"},
    )
    with urlopen(request, timeout=25) as response:
        payload = json.load(response)

    version = payload.get("signature", {}).get("version")
    if payload.get("error"):
        raise ValueError(payload["error"])
    if version not in {"1.2", "1.3"}:
        raise ValueError(f"Unexpected Horizons API version: {version}")

    result = payload.get("result", "")
    before, begin, table = result.partition("$$SOE")
    table, end, _ = table.partition("$$EOE")
    if not begin or not end:
        raise ValueError(before.strip().splitlines()[-1] if before.strip() else "No vector table")

    xyz_km = []
    for row in csv.reader(table.strip().splitlines()):
        # Round off Julian-date serialization error before checking cadence.
        seconds = round((float(row[0]) - JULIAN_DATE_UNIX_EPOCH) * SECONDS_PER_DAY)
        xyz = tuple(float(value) for value in row[2:5])
        if seconds != start.timestamp() + len(xyz_km) * STEP_SECONDS:
            raise ValueError("Horizons returned an unexpected UTC sample time")
        if len(xyz) != 3 or not all(math.isfinite(value) for value in xyz):
            raise ValueError("Horizons returned an invalid position vector")
        xyz_km.append(xyz)

    expected = int((stop - start).total_seconds()) // STEP_SECONDS + 1
    if len(xyz_km) != expected:
        raise ValueError(f"Expected {expected} hourly vectors, received {len(xyz_km)}")
    return xyz_km


def main():
    now = datetime.now(UTC)
    hour = now.replace(minute=0, second=0, microsecond=0)
    start = hour - timedelta(days=44)
    stop = hour + timedelta(days=46)
    try:
        xyz_km = fetch_orbit(start, stop)
    except (URLError, TimeoutError, ValueError, IndexError) as error:
        print(f"::warning::Could not refresh PSP ephemeris: {error}")
        if CACHE.is_file():
            shutil.copyfile(CACHE, OUTPUT)
            print("Published the last successful PSP ephemeris.")
        elif not OUTPUT.is_file():
            print("No cached PSP ephemeris is available.")
        return

    orbit = {
        "start_utc": start.isoformat(),
        "step_seconds": STEP_SECONDS,
        "fetched_utc": now.isoformat(timespec="seconds"),
        "xyz_km": xyz_km,
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    pending = CACHE.with_suffix(".tmp")
    pending.write_text(json.dumps(orbit, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    pending.replace(CACHE)
    shutil.copyfile(CACHE, OUTPUT)
    print(f"Published {len(xyz_km)} hourly PSP vectors from {start} through {stop}.")


if __name__ == "__main__":
    main()
