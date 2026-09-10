FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2

ARG APP_VERSION=0.1.0-beta
ARG BUILD_ID=local

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/srv/app/backend:/srv/app \
    APP_VERSION=${APP_VERSION} \
    BUILD_ID=${BUILD_ID}

WORKDIR /srv/app

# cron is used only by the separate scheduler container.  The serving
# container uses the same immutable image but starts Uvicorn directly.
RUN apt-get update \
    && apt-get install --no-install-recommends -y cron ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --home-dir /home/app app

COPY deploy/requirements.txt /tmp/requirements.txt
RUN python -m pip install -r /tmp/requirements.txt

COPY --chown=app:app backend /srv/app/backend
COPY --chown=app:app grocery_data /srv/app/grocery_data
COPY --chown=app:app deploy /srv/app/deploy
COPY --chown=app:app pyproject.toml /srv/app/pyproject.toml

USER app
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-keep-alive", "30", "--no-access-log"]
