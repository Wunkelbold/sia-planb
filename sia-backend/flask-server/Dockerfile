# syntax=docker/dockerfile:1

FROM python:3.11

WORKDIR /opt/flask-backend

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends dovecot-core locales curl \
    && sed -i '/^# *de_DE.UTF-8 UTF-8/s/^# //' /etc/locale.gen \
    && locale-gen de_DE.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=de_DE.UTF-8 \
    LC_ALL=de_DE.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY . /opt/flask-backend

CMD uwsgi --socket 0.0.0.0:80 --enable-threads --protocol=http -w app:app --stats 0.0.0.0:9191 --stats-http --workers 4 --threads 2
