# syntax=docker/dockerfile:1

FROM ghcr.io/wunkelbold/sia-planb/sia-flask:latest

WORKDIR /opt/flask-backend
COPY . /opt/flask-backend

CMD uwsgi --socket 0.0.0.0:80 --enable-threads --protocol=http -w app:app
