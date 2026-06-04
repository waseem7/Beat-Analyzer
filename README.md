# Latin Beat Analyzer

**Current release:** `0.1.0-alpha.2` — alpha with immutable Docker tags, build metadata, stronger analysis fallback, and live DJ review tools.

A self-hosted Docker web app for human-assisted Latin beatgrid analysis. It is designed for salsa/timba DJ preparation where automatic tools estimate BPM, beats, downbeats, and candidate salsa **1/5** locations, but a fast manual review UI is still required for musical correctness.

## What is included

- Batch audio upload for MP3, WAV, FLAC, M4A, AAC, and OGG.
- Background analysis using `librosa` in the Docker image, with multiple beat-tracker seed attempts, PLP/onset fallback, and no fake 180 BPM placeholder when a trustworthy BPM cannot be estimated.
- BPM and half-time display BPM estimation.
- Beat timestamps, downbeat candidates, salsa 1 markers, and salsa 5 markers.
- Composite confidence scores for BPM, grid, downbeat, salsa 1, and overall analysis.
- Waveform review UI with beatgrid overlays, click-to-seek playhead, beat jumps, phrase loop auditioning, visible app version/build metadata, and a live Web Audio EQ with low/mid/high controls plus live meters.
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

## Alpha mainline and automated publishing

This repo is organized around one long-lived branch: `main`. The alpha release is tracked in [`VERSION`](VERSION), and the alpha policy is documented in [`docs/ALPHA_RELEASE.md`](docs/ALPHA_RELEASE.md).

On every successful push to `main`, GitHub Actions runs tests, builds the Docker image, and publishes these GitHub Container Registry tags:

```text
ghcr.io/waseem7/beat-analyzer:alpha
ghcr.io/waseem7/beat-analyzer:<VERSION>
ghcr.io/waseem7/beat-analyzer:sha-<shortsha>
ghcr.io/waseem7/beat-analyzer:build-<github-run-number>
```

For example, this release publishes tags in this shape:

```text
ghcr.io/waseem7/beat-analyzer:alpha
ghcr.io/waseem7/beat-analyzer:0.1.0-alpha.2
ghcr.io/waseem7/beat-analyzer:sha-7c6251f
ghcr.io/waseem7/beat-analyzer:build-23
```

The `alpha` tag is a moving convenience tag. Use immutable tags for deployments that cache images aggressively.

Pull requests to `main` run tests and Docker build checks without publishing an image.

## Synology Container Manager deployment

Synology Container Manager can silently reuse a locally cached image when a compose file references only a mutable tag such as `alpha`. For Synology, prefer a specific immutable version tag and update the tag when you want to deploy a new release:

```yaml
services:
  beat-analyzer:
    image: ghcr.io/waseem7/beat-analyzer:0.1.0-alpha.2
    container_name: latin-beat-analyzer
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
    restart: unless-stopped
```

If you choose `ghcr.io/waseem7/beat-analyzer:alpha`, remember that it is a moving tag. Synology may require a manual pull, clearing the cached local image, or changing to a fresh immutable tag before it starts the new container image.

After each publish, record these values from the GitHub Actions run summary before updating Synology:

- `VERSION`
- full commit SHA
- `sha-<shortsha>` image tag
- `build-<github-run-number>` image tag
- recommended Synology image tag, usually `ghcr.io/waseem7/beat-analyzer:<VERSION>`
- workflow URL
- whether the workflow's `docker pull ghcr.io/waseem7/beat-analyzer:<VERSION>` verification succeeded

If GHCR access fails from Synology, verify the package visibility in GitHub Packages and make `ghcr.io/waseem7/beat-analyzer` public if needed.

## Run with Docker for local development

```bash
docker compose up --build
```

Open <http://localhost:8000>.

The compose file mounts `./data` into the container:

```text
data/
  music/      uploaded audio files
  analysis/   per-track analysis and correction JSON
  exports/    generated CSV/JSON exports
```

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Run tests:

```bash
pytest
```

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health and build metadata (`status`, `version`, `git_sha`, `build_tag`, `build_date`) |
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
