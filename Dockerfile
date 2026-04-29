# ── Stage 1: Build Vue SPA ────────────────────────────────────────────────────
FROM node:20-alpine AS frontend

WORKDIR /build
COPY tools/gui/package*.json ./
RUN npm ci
COPY tools/gui/ ./
RUN npm run build

# ── Stage 2: Python dependencies + Java + plantuml ───────────────────────────
# This layer is cached as long as pyproject.toml doesn't change.
FROM python:3.13-slim AS deps

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        default-jre-headless \
        libharfbuzz0b \
        libfontconfig1 \
        fonts-dejavu-core \
        graphviz \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps only (no project code yet).
# Copy just pyproject.toml + a minimal src/ stub so pip can resolve the package.
COPY pyproject.toml ./
RUN mkdir -p src/infrastructure/bootstrap && \
    echo '' > src/__init__.py && \
    echo '' > src/infrastructure/__init__.py && \
    echo '' > src/infrastructure/bootstrap/__init__.py && \
    echo 'def main(): pass' > src/infrastructure/bootstrap/get_plantuml.py && \
    pip install --no-cache-dir -e ".[gui]"

# Now copy the real get_plantuml to download the jar.
COPY src/infrastructure/bootstrap/get_plantuml.py src/infrastructure/bootstrap/get_plantuml.py
RUN get-plantuml

# ── Stage 3: Final image with project code ───────────────────────────────────
FROM deps AS runtime

# Overlay actual source + config (deps layer already has the editable install
# pointing at /app/src, so new files are picked up automatically).
COPY config/ config/
COPY src/ src/
RUN get-diagram-runtime --graphviz-mode system

# Embed the pre-built SPA so the server can serve it at /
COPY --from=frontend /build/dist/ tools/gui/dist/

EXPOSE 8000

CMD ["arch-backend", "--repo-root", "/repo", "--host", "0.0.0.0"]
