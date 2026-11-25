# Solar monitor for MkDocs

A scheduled GitHub Actions run fetches solar data, renders six panels, and
publishes the MkDocs site to GitHub Pages. The published page uses local images,
so readers can load it even when a data provider is temporarily unavailable.

## Run locally

From the repository root with Python 3.12:

```sh
python -m pip install -r requirements-solar.txt
python scripts/update_solar.py
python -m mkdocs serve
```

Open <http://127.0.0.1:8000/solar-monitor/>. The updater generates the dashboard
Markdown and PNGs inside `docs/solar-monitor/`. Keep the initial `index.md` in
source control and leave local refresh diffs and PNGs out of commits.

## Set up GitHub Pages

For a new site, copy the starter files into the repository, including
`.github/workflows/solar-pages.yml`. For an existing MkDocs site, keep your
`mkdocs.yml` and add an entry under its existing `nav`, if present:

```yaml
- Solar monitor: solar-monitor/index.md
```

If you already have a Pages workflow, add the dependency install, snapshot
cache, schedule, and refresh step to that workflow before its MkDocs build.
Use your existing build command and site output directory.

Select **GitHub Actions** under **Settings → Pages → Source**. Push to the
default branch or use **Actions → Refresh solar monitor and deploy MkDocs →
Run workflow**. The page will appear at `/solar-monitor/` under the site URL.

## Choose the refresh cadence

Change the workflow cron expression. GitHub uses UTC for the examples below.

| Refresh attempts | Cron |
| --- | --- |
| Every hour at minute 17 (default) | `17 * * * *` |
| Twice an hour | `17,47 * * * *` |
| Every three hours at minute 17 | `17 */3 * * *` |

GitHub can delay scheduled runs, and public repositories can lose scheduled
runs after 60 days without activity. Each panel shows the timestamp supplied by
its data product. The page also shows when the workflow last checked.

## Data products

- **ADAPT GONG** uses the latest readable non-forecast, Carrington-fixed GONG
  FITS file available at the time of the refresh. The map displays the first
  ensemble member and clips the radial field display to ±30 G.
  [NSO archive](https://gong.nso.edu/adapt/maps/gong/)
- **Stanford helioseismic farside** republishes JSOC's composite PNG. The panel
  labels the HTTP modification time as the provider file update. Read the map
  annotation for the data time. You can set `SOLAR_FARSIDE_URL` in the refresh
  step's environment if Stanford moves the PNG.
  [JSOC farside](http://jsoc.stanford.edu/data/farside/)
- **HMI and AIA** download official JSOC FITS products and render them with
  SunPy Map. HMI is a full-disk line-of-sight magnetogram with ±100 G display
  limits. AIA uses the 1K near-real-time 193 Å and 211 Å images with a per-frame
  display stretch.
  [HMI latest](https://jsoc1.stanford.edu/hmi_latest.html) ·
  [AIA NRT archive](https://jsoc1.stanford.edu/data/aia/synoptic/nrt/)
- **OMNI** uses NASA CDAWeb HAPI's one-minute product, time-shifted to Earth's
  bow shock nose. The script charts the most recent 72 hours ending at the
  latest valid record and shows each variable's latest valid time. Missing
  samples remain gaps. Change the window with `--omni-hours 48` on the updater
  command. OMNI's release latency varies.
  [High Resolution OMNI](https://omniweb.gsfc.nasa.gov/form/omni_min.html)

Each source refreshes independently. GitHub Actions restores the previous
successful panels from its cache when available. Individual failures display
the saved image or an unavailable message. If every source fails and the
cache is empty, the workflow exits before deployment.
