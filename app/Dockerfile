# syntax=docker/dockerfile:1

FROM node:24-bookworm-slim AS frontend-build

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src
RUN npm run build


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app \
       --no-create-home --shell /usr/sbin/nologin app

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
