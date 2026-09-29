# Optional diagnostic image only. Never replace the active beta scheduler.
ARG SCHEDULER_IMAGE
FROM ${SCHEDULER_IMAGE}
USER root
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ica-browser
RUN python -m venv --system-site-packages /opt/ica-venv \
    && /opt/ica-venv/bin/pip install --no-cache-dir playwright==1.58.0 \
    && /opt/ica-venv/bin/python -m playwright install --with-deps chromium
USER 10001:10001
WORKDIR /srv/app
