# syntax=docker/dockerfile:1

FROM ghcr.io/wunkelbold/sia-planb/sia-flask:latest

WORKDIR /opt/flask-backend
COPY . /opt/flask-backend
RUN pip install -r requirements.txt

CMD uwsgi --socket 0.0.0.0:80 --enable-threads --protocol=http -w app:app
