FROM node:24-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
COPY graph.json /app/graph.json

RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS backend-build

WORKDIR /app

COPY pyproject.toml uv.lock readme.md ./
COPY src ./src

RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=backend-build /app/.venv /app/.venv
COPY --from=backend-build /app/src /app/src
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    SCINAPSE_FRONTEND_DIST="/app/frontend/dist"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["uvicorn", "scinapse.web:app", "--host", "0.0.0.0", "--port", "8000"]
