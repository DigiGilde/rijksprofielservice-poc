FROM ghcr.io/astral-sh/uv:0.8.0 AS uv
FROM docker.io/python:3.14-slim-trixie AS python

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# ------------------------- Python build stage -------------------------
FROM python AS python-build

ENV UV_CACHE_DIR=/opt/uv-cache/
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV VIRTUAL_ENV=/opt/venv

RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/opt/uv-cache/ \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --active --frozen

# ------------------------- Django run stage -------------------------
FROM python AS django-run

RUN groupadd --gid 1000 app \
    && useradd --gid app --uid 1000 --shell /bin/bash --home-dir /app app

RUN apt-get update && apt-get install --no-install-recommends --assume-yes \
    sudo git bash-completion vim \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-build --chown=app:app /opt/venv /opt/venv
COPY --from=uv /uv /bin/uv

COPY --chown=app:app . /app
RUN chown -R app:app /app

USER app

CMD ["./docker-entrypoint.sh"]
