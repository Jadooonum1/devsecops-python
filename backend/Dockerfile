# syntax=docker/dockerfile:1
# ---- stage 1: install dependencies into a venv -----------------------------
FROM python:3.12-slim AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
COPY requirements.txt .
RUN /opt/venv/bin/pip install -r requirements.txt \
 && /opt/venv/bin/pip uninstall -y pip setuptools wheel

# ---- stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

ARG APP_VERSION=dev
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    APP_VERSION=${APP_VERSION}

# OS patches, then remove the system pip/setuptools: nothing installs
# packages at runtime, and pip's vendored urllib3 was a HIGH CVE in Trivy.
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && (python -m pip uninstall -y pip setuptools wheel || true) \
 && rm -rf /usr/local/lib/python3.12/ensurepip

WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
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
