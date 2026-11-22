# syntax=docker/dockerfile:1

FROM node:24-bookworm-slim AS frontend-build

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src
RUN npm run build


FROM python:3.12-alpine@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install available fixes without bringing Debian administrative tools into runtime.
RUN apk upgrade --no-cache \
    && addgroup -g 10001 app \
    && adduser -D -H -u 10001 -G app -s /sbin/nologin app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check

COPY src ./src
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

RUN find /app/src /app/frontend -type d -exec chmod 0755 {} + \
    && find /app/src /app/frontend -type f -exec chmod 0644 {} +

USER 10001:10001

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "promotion_api.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
