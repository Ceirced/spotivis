# pull official base image
FROM python:3.13.7-slim-bookworm

RUN apt-get update && apt-get -y install curl --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

ENV POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"

RUN curl -sSL https://install.python-poetry.org/ | python

RUN mkdir -p /home/app

WORKDIR /home/app

RUN addgroup --system --gid 1000 app && adduser --system --uid 1000 --group app

COPY poetry.lock pyproject.toml 
RUN poetry install --without dev

COPY flask_app.py config.py boot.sh ./
RUN chmod a+x boot.sh && chown -R app:app /home/app


USER app

# this gets synced in the docker compose but not when building the image alone
COPY app app
COPY migrations migrations
