FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DISPLAY=:99 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3-venv \
        fluxbox \
        novnc \
        websockify \
        x11-utils \
        x11vnc \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Создаём отдельное окружение, чтобы pip не конфликтовал
# с системными пакетами Ubuntu.
RUN python3 -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/python" -m pip install --upgrade \
        pip \
        setuptools \
        wheel

COPY pyproject.toml README.md ./
COPY app ./app

RUN "${VIRTUAL_ENV}/bin/python" -m pip install .

COPY scripts ./scripts
COPY tests ./tests
COPY healthcheck.py docker-entrypoint.sh Makefile ./

# Удаляем Windows-переносы CRLF и выдаём право на запуск.
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh \
    && chmod +x /app/docker-entrypoint.sh \
    && mkdir -p \
        /app/runtime/data \
        /app/runtime/browser-profile \
        /app/runtime/screenshots \
        /app/runtime/logs

ENTRYPOINT ["/app/docker-entrypoint.sh"]

CMD ["/opt/venv/bin/python", "-m", "app.main"]