# syntax=docker/dockerfile:1

FROM python:3.14.8-slim-trixie

WORKDIR /opt/flask-backend

COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --upgrade \
        pip==26.2.1 setuptools==84.0.0 wheel==0.48.0 \
    && python -m pip install --no-cache-dir -r /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends locales curl \
    && sed -i '/^# *de_DE.UTF-8 UTF-8/s/^# //' /etc/locale.gen \
    && locale-gen de_DE.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=de_DE.UTF-8 \
    LC_ALL=de_DE.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY . /opt/flask-backend

CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "4", "--threads", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "app:app"]
