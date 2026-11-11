# Single image: the React build is served by Django (WhiteNoise), so there is one service to host.

# ---- 1. Build the React app -------------------------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Django API + static front end ---------------------------------------------------------
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=web /web/dist ./frontend_dist

RUN useradd --create-home --uid 1001 app && chown -R app /app
USER app

EXPOSE 8000
# Threads (not just workers) because each request mostly waits on third-party APIs.
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers 2 --threads 8 --timeout 120"]
