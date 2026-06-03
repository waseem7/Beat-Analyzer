# Latin Beat Analyzer

A self-hosted Docker web app for human-assisted Latin beatgrid analysis. It is designed for salsa/timba DJ preparation where automatic tools can estimate BPM, beats, downbeats, and candidate salsa **1/5** locations, but a fast manual review UI is still required for musical correctness.

## What is included

- Batch audio upload for MP3, WAV, FLAC, M4A, AAC, and OGG.
- Background analysis using `librosa` in the Docker image, with a low-confidence fallback grid if automatic analysis fails.
- BPM and half-time display BPM estimation.
- Beat timestamps, downbeat candidates, salsa 1 markers, and salsa 5 markers.
- Composite confidence scores for BPM, grid, downbeat, salsa 1, and overall analysis.
- Waveform review UI with beatgrid overlays.
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
- Persistent local storage under `./data` for music, analysis JSON, and exports.

## Run with Docker

```bash
docker compose up --build
```

Open <http://localhost:8000>.

The included compose file is configured for the target self-hosted deployment and mounts persistent storage into `/data`:

```text
/volume1/docker/containers/beat-analyzer:/data
/volume1/data/media/beat-analyzer:/import
```

Inside the container, analysis state is stored under:

```text
/data/music/      uploaded audio files
/data/analysis/   per-track analysis and correction JSON
/data/exports/    generated CSV/JSON exports
```

The container exposes internal port `8000`, maps `8000:8000/tcp`, and includes a Docker healthcheck that calls `/api/health`.

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

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health check |
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
