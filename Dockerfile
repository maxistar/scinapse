FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

WORKDIR /app

COPY pyproject.toml uv.lock readme.md ./
COPY src ./src

RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["uvicorn", "scinapse.api:app", "--host", "0.0.0.0", "--port", "8000"]
