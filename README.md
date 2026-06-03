# Latin Beat Analyzer

A self-hosted Docker web app for human-assisted Latin beatgrid analysis. It is designed for salsa/timba DJ preparation where automatic tools can estimate BPM, beats, downbeats, and candidate salsa **1/5** locations, but a fast manual review UI is still required for musical correctness.

## What is included

- Batch audio upload for MP3, WAV, FLAC, M4A, AAC, and OGG.
- `/import` scanning for existing NAS music libraries without browser upload.
- Background analysis using `librosa` in the Docker image, with a low-confidence fallback grid if automatic analysis fails.
- BPM and half-time display BPM estimation.
- Beat timestamps, downbeat candidates, salsa 1 markers, and salsa 5 markers.
- Composite confidence scores for BPM, grid, downbeat, salsa 1, and overall analysis.
- Modern review UI with dark/light/system theme, accent color, queue filters, sorting, compact mode, and server settings display.
- Manual correction buttons:
  - Set current playhead as 1
  - Set current playhead as 5
  - Swap 1 / 5
  - Shift +/- 1 beat
  - Shift +/- 4 beats
  - Half/double BPM
  - Mark reviewed
- CSV and JSON export.
- Optional MP3 BPM/comment tag writing through `mutagen`.
- Split persistent storage under `/data/music`, `/data/analysis`, and `/data/exports`.

## Security note

Latin Beat Analyzer currently has **no built-in authentication or user management**. Keep it LAN-only, bind it behind a trusted reverse proxy, or protect remote access with Cloudflare Access, a VPN, Authelia, Authentik, or another authentication gateway before exposing it to the internet.

## Run with Docker

```bash
docker compose up --build
```

Open <http://localhost:8000>.

The official `compose.yaml` is NAS-friendly but configurable through environment variables. By default it matches a Synology-style deployment:

```text
container_name: beat-analyzer
user: 1027:100
PUID=1027
PGID=100
TZ=Asia/Riyadh
UMASK=022
network_mode=synobridge
restart=always
security_opt=no-new-privileges:true
```

The compose file uses split persistent mounts instead of a single `./data:/data` mount:

```text
/volume1/docker/containers/beat-analyzer/music:/data/music
/volume1/docker/containers/beat-analyzer/analysis:/data/analysis
/volume1/docker/containers/beat-analyzer/exports:/data/exports
/volume1/data/media/beat-analyzer:/import
```

For other NAS/Linux setups, override any of these values before running Compose:

```bash
export PUID=1000
export PGID=1000
export TZ=UTC
export BEAT_ANALYZER_NETWORK_MODE=bridge
export BEAT_ANALYZER_MUSIC_DIR=/srv/beat-analyzer/music
export BEAT_ANALYZER_ANALYSIS_DIR=/srv/beat-analyzer/analysis
export BEAT_ANALYZER_EXPORTS_DIR=/srv/beat-analyzer/exports
export BEAT_ANALYZER_IMPORT_DIR=/srv/music
export BEAT_ANALYZER_PORT=8000
docker compose up -d
```

Inside the container, analysis state is stored under:

```text
/data/music/      uploaded audio files
/data/analysis/   per-track analysis and correction JSON
/data/exports/    generated CSV/JSON exports
/import/          optional mounted music library to scan
```

The container exposes internal port `8000`, maps `8000:8000/tcp` by default, and includes Dockerfile and Compose healthchecks that call `/api/health`.

## Docker validation

Run these checks after changing Docker or deployment files:

```bash
docker compose config
docker compose build
docker compose up -d
curl http://localhost:8000/api/health
```

The expected health response is:

```json
{"status":"ok"}
```

## Importing existing NAS music

Mount your existing library under `/import` using `BEAT_ANALYZER_IMPORT_DIR` or the compose volume. In the UI, click **Scan /import**. The app registers supported audio files in place, analyzes them in the background, and avoids duplicate imports by source path.

Supported extensions are MP3, WAV, FLAC, M4A, AAC, and OGG. Imported files are served and analyzed from `/import`; uploaded files are stored in `/data/music`.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DATA_DIR=./data IMPORT_DIR=./import uvicorn backend.app.main:app --reload
```

Run tests:

```bash
pytest
```

## Validation

Use the validation helper before opening or updating a PR:

```bash
./scripts/validate.sh
```

The script compiles the backend, runs pytest, and runs Docker Compose validation/build when Docker is available. The repository also includes a GitHub Actions workflow that runs Python tests and Docker Compose build checks on pushes and pull requests.

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/settings` | Runtime directories, auth flag, supported extensions |
| `POST` | `/api/import/scan` | Scan mounted `/import` audio files and queue analysis |
| `POST` | `/api/tracks` | Upload and analyze one audio file |
| `GET` | `/api/tracks` | List review queue |
| `GET` | `/api/tracks/{id}` | Get full track analysis/corrections |
| `POST` | `/api/tracks/{id}/analyze` | Re-run analysis |
| `POST` | `/api/tracks/{id}/corrections` | Apply manual correction action |
| `POST` | `/api/tracks/{id}/write-tags` | Write BPM/comment tags to the audio file |
| `GET` | `/api/exports/tracks.csv` | Export library summary CSV |
| `GET` | `/api/tracks/{id}/exports/beats.csv` | Export detailed beat CSV |
| `GET` | `/api/tracks/{id}/exports/analysis.json` | Export master analysis JSON |

## Important product note

This app intentionally treats salsa/timba 1 detection as **candidate analysis plus manual confirmation**. The software can estimate a likely first clean 1 and a corresponding 5, but the musical 1 can be ambiguous in Latin music. The review tools are therefore part of the core workflow, not a fallback.

## Future extensions

- BeatNet/Essentia worker backend for stronger beat/downbeat analysis.
- Redis/Celery job queue for large libraries.
- Rekordbox or VirtualDJ bridge exports.
- Variable-tempo anchors.
- Correction memory by artist/style.
- Latin phrase/clave-aware model trained from reviewed tracks.
