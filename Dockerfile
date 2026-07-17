# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS dependencies

ENV VIRTUAL_ENV=/opt/venv \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN python -m venv "${VIRTUAL_ENV}"

WORKDIR /build
COPY requirements.txt requirements-ui.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-ui.txt \
    && python -m pip check


FROM python:3.11-slim AS runtime

ARG APP_VERSION=1.0.0-rc2

LABEL org.opencontainers.image.title="Satellite Acquisition Planner" \
      org.opencontainers.image.description="Planowanie akwizycji satelitarnych SAR i EO" \
      org.opencontainers.image.version="${APP_VERSION}"

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=/opt/satplan \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    XDG_CACHE_HOME=/tmp/.cache \
    MPLCONFIGDIR=/tmp/matplotlib

RUN groupadd --gid 10001 satplan \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin satplan

COPY --from=dependencies /opt/venv /opt/venv

WORKDIR /opt/satplan
COPY --chown=satplan:satplan . .

USER satplan

RUN python -m app.cli check \
    && python -m app.cli audit --strict \
    && python -m app.cli health --skip-http --quiet

EXPOSE 8501
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["python", "-m", "app.cli", "health", "--quiet"]

CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
