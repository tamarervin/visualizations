"""Fetch source data and build the solar monitor page for MkDocs."""

import argparse
from collections import defaultdict
import csv
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import escape
from html.parser import HTMLParser
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

import astropy.units as u
import matplotlib

matplotlib.use("Agg")
from matplotlib import dates as mdates, pyplot as plt
from matplotlib.colors import AsinhNorm, Normalize
import numpy as np
from PIL import Image
from sunpy.map import Map

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "solar-monitor"
CACHE = ROOT / ".solar-cache"
GONG = "https://gong.nso.edu/adapt/maps/gong/"
AIA = "https://jsoc1.stanford.edu/data/aia/synoptic/nrt/"
HMI = "https://jsoc1.stanford.edu/data/hmi/images/latest/HMI_latest_Mag.fits"
FARSIDE = "http://jsoc.stanford.edu/data/farside/Recent/Composite_Map.png"
HAPI = "https://cdaweb.gsfc.nasa.gov/hapi/"
OMNI = "OMNI_HRO_1MIN"
OMNI_PARAMETERS = ("F", "BZ_GSM", "flow_speed", "proton_density")
OMNI_LABELS = ("|B|", "Bz GSM", "Speed", "Proton density")
ADAPT_NAME = re.compile(r"adapt403\d{2}_\d{2}\w\d{3}_(\d{12})_[ai]\d{8}[a-z]\d\.fts\.gz")
AIA_NAME = re.compile(r"AIA(\d{8}_\d{6})_(\d{4})\.fits(?:\.gz)?")


class Links(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.hrefs = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.extend(value for name, value in attrs if name == "href" and value)


def fetch(url, limit=112 * 1024 * 1024):
    request = Request(url, headers={"User-Agent": "MkDocs solar monitor/1.0"})
    with urlopen(request, timeout=30) as response:
        content = response.read(limit + 1)
        if len(content) > limit:
            raise ValueError(f"Response exceeded download limit for {url}")
        return content, response.headers


def links(url):
    content, _ = fetch(url, limit=16 * 1024 * 1024)
    return Links(content.decode("utf-8")).hrefs


def date_label(value):
    return value.strftime("%Y-%m-%d %H:%M UTC")


def read_time(value):
    return datetime.fromisoformat(value).astimezone(UTC)


def read_map(url, temp, **kwargs):
    content, _ = fetch(url)
    # Preserve the extension so SunPy can identify compressed FITS files.
    path = temp / url.rsplit("/", 1)[-1]
    path.write_bytes(content)
    return Map(path, **kwargs)


def write_figure(fig, path):
    try:
        fig.savefig(path, dpi=145, facecolor="white")
    finally:
        plt.close(fig)


def render_adapt(out, now, temp):
    candidates = []
    for year in sorted({now.year, (now - timedelta(days=7)).year}, reverse=True):
        directory = f"{GONG}{year}/"
        try:
            for name in links(directory):
                match = ADAPT_NAME.fullmatch(name)
                if match:
                    when = datetime.strptime(match[1], "%Y%m%d%H%M").replace(tzinfo=UTC)
                    if when <= now:
                        candidates.append((when, urljoin(directory, name)))
        except OSError as exc:
            logging.warning("ADAPT directory %s: %s", year, exc)
    for when, url in sorted(candidates, reverse=True)[:3]:
        try:
            smap = read_map(url, temp, hdus=0)
            break
        except (OSError, ValueError) as exc:
            logging.warning("ADAPT file %s: %s", url, exc)
    else:
        raise ValueError("No readable Carrington-fixed GONG ADAPT map")

    fig = plt.figure(figsize=(9.4, 4.6), layout="constrained")
    ax = fig.add_subplot(projection=smap)
    artist = smap.plot(axes=ax, cmap="RdBu_r", vmin=-30, vmax=30, title=False)
    ax.set_title("")
    ax.set_xlabel("Carrington longitude")
    ax.set_ylabel("Carrington latitude")
    fig.colorbar(artist, ax=ax, label="Radial field (G)", shrink=0.84, extend="both")
    write_figure(fig, out)
    return when, "Map time", url, "Carrington-fixed radial field, ADAPT ensemble member 1."


def render_farside(out, now, temp):
    url = os.environ.get("SOLAR_FARSIDE_URL", FARSIDE)
    content, headers = fetch(url, limit=10 * 1024 * 1024)
    with Image.open(BytesIO(content)) as image:
        image.save(out, format="PNG")
    modified = headers.get("Last-Modified")
    when = parsedate_to_datetime(modified).astimezone(UTC) if modified else None
    return when, "Provider file updated", url, (
        "Stanford SDO/HMI composite. The map annotates its own data time."
    )


def aia_candidates(now):
    directory_index, _ = fetch(AIA + "image_times.json")
    latest = datetime.strptime(json.loads(directory_index)["last"], "%Y%m%d_%H%M%S")
    latest = latest.replace(tzinfo=UTC)
    candidates = defaultdict(list)
    for offset in range(3):
        hour = latest - timedelta(hours=offset)
        directory = AIA + hour.strftime("%Y/%m/%d/H%H00/")
        try:
            filenames = links(directory)
        except OSError as exc:
            logging.warning("AIA directory %s: %s", directory, exc)
            continue
        for name in filenames:
            match = AIA_NAME.fullmatch(name)
            if match:
                when = datetime.strptime(match[1], "%Y%m%d_%H%M%S").replace(tzinfo=UTC)
                if when <= now:
                    candidates[int(match[2])].append((when, urljoin(directory, name)))
    return candidates


def render_disk(smap, out, wavelength=None):
    data = np.asarray(smap.data, dtype=float)
    valid = data[np.isfinite(data)]
    if not valid.size:
        raise ValueError("FITS image has no finite pixels")
    fig = plt.figure(figsize=(5.5, 5.5), layout="constrained")
    ax = fig.add_subplot(projection=smap)
    if wavelength:
        vmax = max(1, np.percentile(valid, 99.5))
        smap.plot(axes=ax, cmap=f"sdoaia{wavelength}", title=False,
                  norm=AsinhNorm(linear_width=vmax / 20, vmin=0, vmax=vmax))
    else:
        artist = smap.plot(axes=ax, cmap="gray", norm=Normalize(vmin=-100, vmax=100), title=False)
        fig.colorbar(artist, ax=ax, orientation="horizontal", label="LOS field (G)",
                     shrink=0.85, extend="both", pad=0.035)
    ax.set_axis_off()
    ax.set_title("")
    write_figure(fig, out)


def render_hmi(out, now, temp):
    smap = read_map(HMI, temp)
    if max(smap.data.shape) > 1200:
        smap = smap.resample([1024, 1024] * u.pixel)
    smap = smap.rotate()
    render_disk(smap, out)
    return smap.date.utc.to_datetime(timezone=UTC), "Observation", HMI, (
        "SDO/HMI full-disk line-of-sight photospheric field."
    )


def render_aia(out, now, temp, wavelength, candidates):
    for when, url in sorted(candidates.get(wavelength, []), reverse=True)[:3]:
        try:
            smap = read_map(url, temp)
            render_disk(smap, out, wavelength=wavelength)
            return smap.date.utc.to_datetime(timezone=UTC), "Observation", url, (
                "SDO/AIA near-real-time 1K EUV image with an asinh display stretch."
            )
        except (OSError, ValueError) as exc:
            logging.warning("AIA file %s: %s", url, exc)
    raise ValueError(f"No readable AIA {wavelength} Å image")


def hapi(endpoint, **params):
    return fetch(f"{HAPI}{endpoint}?{urlencode(params)}", limit=8 * 1024 * 1024)[0]


def omni_data(now, hours):
    info = json.loads(hapi("info", id=OMNI))
    end = min(read_time(info["stopDate"]), now)
    by_name = {parameter["name"]: parameter for parameter in info["parameters"]}
    fills = np.array([float(by_name[name]["fill"]) for name in OMNI_PARAMETERS])
    # HAPI coverage can end in rows made entirely of fill values.
    start = end - timedelta(days=14, hours=hours)
    body = hapi("data", id=OMNI, parameters=",".join(OMNI_PARAMETERS),
                **{"time.min": start.isoformat(timespec="seconds").replace("+00:00", "Z"),
                   "time.max": end.isoformat(timespec="seconds").replace("+00:00", "Z"),
                   "format": "csv"})
    rows = {}
    for row in csv.reader(body.decode("ascii").splitlines()):
        if len(row) != 5:
            continue
        values = np.array(row[1:], dtype=float)
        values[(values == fills) | ~np.isfinite(values)] = np.nan
        rows[read_time(row[0])] = values
    latest = max((when for when, row in rows.items() if np.isfinite(row).any()), default=None)
    if latest is None:
        raise ValueError("No valid OMNI data in the requested lookback")
    times = [latest - timedelta(minutes=i) for i in range(hours * 60, -1, -1)]
    values = np.array([rows.get(when, [np.nan] * 4) for when in times])
    return times, values


def render_omni(out, now, temp, hours):
    times, values = omni_data(now, hours)
    fig, axes = plt.subplots(3, 1, figsize=(10, 6.1), sharex=True, layout="constrained")
    axes[0].plot(times, values[:, 2], color="#245b85", linewidth=0.9)
    axes[1].plot(times, values[:, 3], color="#14766f", linewidth=0.9)
    axes[2].plot(times, values[:, 0], label="|B|", color="#68389b", linewidth=0.9)
    axes[2].plot(times, values[:, 1], label="Bz GSM", color="#b14a24", linewidth=0.9)
    axes[2].axhline(0, color="gray", linewidth=0.6)
    axes[2].legend(loc="best", frameon=False, ncol=2)
    for ax, label in zip(axes, ("Speed (km/s)", "Proton density (cm⁻³)", "IMF (nT)"), strict=True):
        ax.set_ylabel(label)
        ax.grid(alpha=0.22)
        ax.set_xlim(times[0], times[-1])
    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    axes[2].xaxis.set_major_locator(locator)
    axes[2].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    axes[2].set_xlabel("Bow shock nose time (UTC)")
    write_figure(fig, out)
    last = []
    for i, label in enumerate(OMNI_LABELS):
        valid = np.flatnonzero(np.isfinite(values[:, i]))
        last.append(f"{label}: {date_label(times[valid[-1]]) if valid.size else 'no data in window'}")
    details = f"Latest {hours} hours of one-minute OMNI. Latest valid samples — " + " · ".join(last)
    return times[-1], "Latest valid sample", "https://omniweb.gsfc.nasa.gov/form/omni_min.html", details


def update_panel(key, renderer, now, temp, *args):
    image = CACHE / f"{key}.png"
    meta = CACHE / f"{key}.json"
    previous = json.loads(meta.read_text()) if image.exists() and meta.exists() else {}
    try:
        candidate = temp / f"{key}.png"
        when, time_label, url, detail = renderer(candidate, now, temp, *args)
        if previous.get("time") and (when is None or when < read_time(previous["time"])):
            raise ValueError("Provider returned an older snapshot")
        record = {
            "time": when.isoformat() if when else None,
            "time_label": time_label,
            "source": url,
            "detail": detail,
        }
        candidate.replace(image)
        pending = temp / f"{key}.json"
        pending.write_text(json.dumps(record), encoding="utf-8")
        pending.replace(meta)
        logging.info("%s: %s", key, record["time"] or "provider time unavailable")
        return record, False
    except Exception:
        logging.exception("%s refresh failed", key)
        return previous, True


def panel_html(key, title, status, now, source, stale_after_hours):
    record, failed = status
    source = escape(record.get("source", source), quote=True)
    if record:
        when = read_time(record["time"]) if record["time"] else None
        timestamp = date_label(when) if when else "unavailable"
        note = ""
        if failed:
            note = " · Showing last successful refresh"
        if when and now - when > timedelta(hours=stale_after_hours):
            note += " · Older than " + str(stale_after_hours) + " h"
        body = (
            f"<p><strong>{escape(record['time_label'])}:</strong> {timestamp}{note}</p>\n"
            f'<a href="{key}.png"><img src="{key}.png" alt="{escape(title)}" '
            f'loading="lazy" style="width:100%;height:auto"></a>\n'
            f"<p>{escape(record['detail'])}</p>"
        )
    else:
        body = "<p>Source unavailable. A successful refresh will populate this panel.</p>"
    return (
        f'<section style="min-width:0"><h3>{escape(title)}</h3>\n{body}\n'
        f'<p><a href="{source}">Source data</a></p></section>'
    )


def write_page(now, results):
    titles = {
        "omni": ("OMNI solar wind", "https://omniweb.gsfc.nasa.gov/form/omni_min.html", 72),
        "aia193": ("SDO/AIA 193 Å", AIA, 3),
        "aia211": ("SDO/AIA 211 Å", AIA, 3),
        "hmi": ("SDO/HMI magnetogram", HMI, 3),
        "adapt": ("ADAPT GONG magnetogram", GONG, 12),
        "farside": ("Stanford helioseismic farside map", FARSIDE, 36),
    }
    panels = {key: panel_html(key, title, results[key], now, source, age)
              for key, (title, source, age) in titles.items()}
    for key, (record, _) in results.items():
        if record:
            shutil.copyfile(CACHE / f"{key}.png", PAGE / f"{key}.png")

    grid = 'style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:1rem"'
    page = "\n\n".join([
        "# Solar monitor",
        f"Last refresh attempt {date_label(now)}. Observation times are shown for each product.",
        "## Solar wind at Earth",
        panels["omni"],
        "## Earth-facing Sun",
        f"<div {grid}>\n{panels['aia193']}\n{panels['aia211']}\n{panels['hmi']}\n</div>",
        "## Global and farside maps",
        panels["adapt"],
        panels["farside"],
    ])
    (PAGE / "index.md").write_text(page + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--omni-hours", type=int, default=72, choices=range(1, 169), metavar="1–168")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    now = datetime.now(UTC)
    PAGE.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=CACHE) as directory:
        temp = Path(directory)
        try:
            candidates = aia_candidates(now)
        except (OSError, ValueError, KeyError):
            logging.exception("AIA discovery failed")
            candidates = {}
        results = {
            "adapt": update_panel("adapt", render_adapt, now, temp),
            "farside": update_panel("farside", render_farside, now, temp),
            "hmi": update_panel("hmi", render_hmi, now, temp),
            "aia193": update_panel("aia193", render_aia, now, temp, 193, candidates),
            "aia211": update_panel("aia211", render_aia, now, temp, 211, candidates),
            "omni": update_panel("omni", render_omni, now, temp, args.omni_hours),
        }
    if not any(record for record, _ in results.values()):
        parser.exit(1, "All data feeds failed and no previous snapshots were available.\n")
    write_page(now, results)


if __name__ == "__main__":
    main()
