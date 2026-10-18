# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

ARG APP_VERSION=dev
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${APP_VERSION}

WORKDIR /app

# OS patches first, then dependencies (cached until requirements.txt changes)
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && pip install -r requirements.txt

COPY alembic.ini docker-entrypoint.sh ./
COPY alembic ./alembic
COPY app ./app

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
 && chmod 0555 docker-entrypoint.sh
USER 10001

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
