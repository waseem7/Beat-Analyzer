#!/usr/bin/env bash
set -euo pipefail

python -m compileall backend
python -m pytest

if command -v docker >/dev/null 2>&1; then
  docker compose config
  docker compose build
else
  echo "docker is not installed; skipping docker compose config/build" >&2
fi
