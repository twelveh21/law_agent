# Match the Python major/minor version used by this project.
FROM python:3.13-slim-bookworm

# Use the same uv version as the current local environment.
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Native libraries/compiler for existing dependencies in the project lockfile.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates build-essential libgomp1 libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first so code changes can reuse this build layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

# Copy code only. Data and credentials are supplied at runtime.
COPY app ./app
COPY scripts ./scripts

RUN useradd --create-home --uid 1000 agent \
    && mkdir -p /var/lib/law-agent/db /var/lib/law-agent/data /var/lib/law-agent/chroma \
    && chown -R agent:agent /var/lib/law-agent
USER agent

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).close()"]

# One worker: the current embedded Qdrant directory has a single process owner.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
