FROM python:3.11-slim

ARG VERSION="0.1.0-alpha.2"
ARG GIT_SHA="unknown"
ARG BUILD_TAG="local"
ARG BUILD_DATE="unknown"

LABEL org.opencontainers.image.source="https://github.com/waseem7/Beat-Analyzer" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.title="Beat Analyzer"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NUMBA_CACHE_DIR=/tmp/numba-cache \
    MPLCONFIGDIR=/tmp/matplotlib \
    BEAT_ANALYZER_VERSION="${VERSION}" \
    BEAT_ANALYZER_GIT_SHA="${GIT_SHA}" \
    BEAT_ANALYZER_BUILD_TAG="${BUILD_TAG}" \
    BEAT_ANALYZER_BUILD_DATE="${BUILD_DATE}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY VERSION .
COPY backend ./backend
RUN mkdir -p /data/music /data/analysis /data/exports /tmp/numba-cache /tmp/matplotlib
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
