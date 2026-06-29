FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DISPLAY=:99

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fluxbox \
        novnc \
        python3-venv \
        websockify \
        x11-utils \
        x11vnc \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv

RUN python -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/python" -m pip install --upgrade \
        pip \
        setuptools \
        wheel

ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app

RUN python -m pip install .

COPY scripts ./scripts
COPY tests ./tests
COPY healthcheck.py docker-entrypoint.sh Makefile ./

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p \
        /app/runtime/data \
        /app/runtime/browser-profile \
        /app/runtime/screenshots \
        /app/runtime/logs

ENTRYPOINT ["/app/docker-entrypoint.sh"]

CMD ["python", "-m", "app.main"]