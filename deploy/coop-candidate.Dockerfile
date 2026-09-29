# Isolated Coop candidate runtime; no daemon, cron or production activation.
# BROWSER_BASE must be a recorded immutable local image ID/digest.
ARG BROWSER_BASE
FROM ${BROWSER_BASE}
USER root
COPY --chown=10001:10001 backend/app /srv/app/backend/app
COPY --chown=10001:10001 grocery_data/app /srv/app/grocery_data/app
COPY --chown=10001:10001 grocery_data/scripts /srv/app/grocery_data/scripts
COPY --chown=10001:10001 grocery_data/__main__.py /srv/app/grocery_data/__main__.py
COPY --chown=10001:10001 deploy/scripts /srv/app/deploy/scripts
COPY release-wheels /opt/coop-wheels
COPY grocery_data/requirements-coop-candidate.txt /opt/coop-requirements.txt
RUN /opt/ica-venv/bin/python -m pip install --no-index --find-links=/opt/coop-wheels -r /opt/coop-requirements.txt
ENV PATH=/opt/ica-venv/bin:$PATH \
    PYTHONPATH=/srv/app/backend:/srv/app \
    PYTHONDONTWRITEBYTECODE=1 \
    ICA_FLYER_PAID_ENABLED=false \
    ICA_FLYER_VISUAL_COMMAND_JSON= \
    ICA_STRUCTURED_OFFERS_ENABLED=false
RUN /opt/ica-venv/bin/python -c "import importlib.metadata; assert importlib.metadata.version('playwright') == '1.58.0'"
RUN /opt/ica-venv/bin/python -c "import bs4, pymupdf; from grocery_data.app.services.coop_municipal_refresh import update_selection"
USER 10001:10001
WORKDIR /srv/app
ENTRYPOINT ["/opt/ica-venv/bin/python", "-m", "grocery_data.scripts.collect_coop_release"]
CMD ["--help"]
