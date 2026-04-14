# ── Stage 1: Build Vue SPA ────────────────────────────────────────────────────
FROM node:20-alpine AS frontend

WORKDIR /build
COPY tools/gui/package*.json ./
RUN npm ci
COPY tools/gui/ ./
RUN npm run build

# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# Java runtime — required for plantuml diagram verification and rendering.
# default-jre-headless on Debian bookworm resolves to OpenJDK 17.
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Install Python package with GUI extras.
# Editable install keeps __file__ at /app/src/… so relative path resolution
# for tools/plantuml.jar and tools/gui/dist/ works correctly at runtime.
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir -e ".[gui]"

# Download and SHA-256-verify plantuml.jar from Maven Central.
# Version is pinned in src/tools/get_plantuml.py; bump it there to upgrade.
RUN get-plantuml

# Embed the pre-built SPA so the server can serve it at /
COPY --from=frontend /build/dist/ tools/gui/dist/

EXPOSE 8000

# Mount your architecture repository at /repo via -v or docker-compose volumes.
# The server also serves the built SPA from tools/gui/dist/.
CMD ["sdlc-gui-server", "--repo-root", "/repo", "--host", "0.0.0.0"]
