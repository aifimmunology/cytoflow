# ── cytoflowweb Dockerfile ────────────────────────────────────────────────────
#
# Builds the cytoflowweb FastAPI + Dash application using pixi to manage the
# conda/PyPI environment.  The Logicle C++ extension is compiled during build.
#
# Build:
#   docker build -t cytoflowweb .
#
# Run (standalone):
#   docker run -p 8000:8000 cytoflowweb
#
# Preferred: use docker compose (see docker-compose.yml)

FROM debian:bookworm-slim

# ── System build dependencies ─────────────────────────────────────────────────
# build-essential + swig are needed to compile the Logicle C++ extension.
# curl + ca-certificates are needed to install pixi.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl \
       ca-certificates \
       build-essential \
       swig \
    && rm -rf /var/lib/apt/lists/*

# ── Install pixi ──────────────────────────────────────────────────────────────
ENV PIXI_HOME=/usr/local/pixi
RUN curl -fsSL https://pixi.sh/install.sh | PIXI_HOME=$PIXI_HOME bash
ENV PATH="$PIXI_HOME/bin:$PATH"

# ── Application working directory ─────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies via pixi ──────────────────────────────────────
# Copy only the dependency manifests first so this layer is cached as long as
# dependencies don't change (i.e. independently of source code changes).
COPY pixi.toml pixi.lock* ./

# Install the 'web' environment.  If pixi.lock exists it is used (--frozen);
# otherwise the solver runs and produces a fresh lock.
RUN if [ -f pixi.lock ]; then \
      pixi install -e web --frozen; \
    else \
      pixi install -e web; \
    fi

# ── Patch fcsparser for NumPy 2.0 compatibility ───────────────────────────────
# PyPI fcsparser 0.2.x calls ndarray.newbyteorder() which was removed in
# NumPy 2.0. Replace with the equivalent view() call.
RUN FCSPARSER_API=$(pixi run -e web python -c \
        "import fcsparser, os; print(os.path.join(os.path.dirname(fcsparser.__file__), 'api.py'))") \
    && sed -i \
        's/data = data\.byteswap()\.newbyteorder()/data = data.byteswap().view(data.dtype.newbyteorder())/' \
        "$FCSPARSER_API"

# ── Copy source and compile C++ extension ────────────────────────────────────
COPY . .

RUN pixi run -e web pip install --no-build-isolation -e .

# ── Runtime configuration ─────────────────────────────────────────────────────
# Defaults are suitable for running inside the container.
# Override via docker-compose.yml `environment:` block.
ENV CYTOFLOWWEB_HOST=0.0.0.0 \
    CYTOFLOWWEB_PORT=8000 \
    CYTOFLOWWEB_API_BASE=http://localhost:8000/api \
    CYTOFLOWWEB_UPLOAD_ROOT=/data/uploads \
    CYTOFLOWWEB_MAX_SESSIONS=50 \
    CYTOFLOWWEB_LOG_LEVEL=info

# Persistent volume for uploaded FCS files
RUN mkdir -p /data/uploads
VOLUME ["/data/uploads"]

EXPOSE 8000

# Health check — used by Docker and docker compose
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["pixi", "run", "-e", "web", "python", "-m", "cytoflowweb"]
