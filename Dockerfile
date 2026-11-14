# AutoDocs web demo: saved runs for everyone, live runs on the visitor's own Gemini key.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_HTTP_TIMEOUT=120

COPY pyproject.toml uv.lock README.md ./
# The cache mount keeps downloads between builds, so a failed download isn't fetched twice.
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY autodocs ./autodocs
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# The repo the demo documents: ShopLite, with the three class branches as local branches.
COPY demo/shoplite.bundle /tmp/shoplite.bundle
RUN git clone -q /tmp/shoplite.bundle demo/shoplite \
    && cd demo/shoplite \
    && for b in feat/coupon-stacking fix/stock-race feat/review-moderation; do \
         git branch -q "$b" "origin/$b"; done
COPY runs/*.json runs/

RUN useradd --create-home autodocs && chown -R autodocs runs demo  # git refuses repos owned by another user
USER autodocs
ENV PATH="/app/.venv/bin:$PATH" PORT=8080 \
    AUTODOCS_DEMO_REPO=/app/demo/shoplite AUTODOCS_RUNS_DIR=/app/runs
EXPOSE 8080
# One worker (runs are slow and per-request); timeout above the 120 s live-run limit.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 180 'autodocs.web:create_app()'"]
