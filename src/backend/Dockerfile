# Build and run the API with uv (D1).
#
# Dependencies are installed in their own layer, before the source is copied, so a
# code change does not re-resolve the dependency tree. --frozen makes the build fail
# if uv.lock is stale rather than silently resolving something different from what was
# tested locally.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
RUN uv sync --frozen --no-dev

# Put the project venv first so `python` and `uvicorn` resolve without `uv run`.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "logistics_analytics.main:create_default_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
