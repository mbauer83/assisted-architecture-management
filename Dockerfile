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

# Install Python package (source + gui extras) — separate COPY for cache efficiency
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir -e ".[gui]"

# Embed the pre-built SPA so the server can serve it at /
COPY --from=frontend /build/dist/ tools/gui/dist/

EXPOSE 8000

# Mount your architecture repository at /repo via -v or docker-compose volumes.
# The server also serves the built SPA from tools/gui/dist/.
CMD ["sdlc-gui-server", "--repo-root", "/repo", "--host", "0.0.0.0"]
