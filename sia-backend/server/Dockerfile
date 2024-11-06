# syntax=docker/dockerfile:1

FROM ghcr.io/wunkelbold/sia-planb/sia-flask:latest

COPY . /opt/flask-backend
EXPOSE 5005

CMD uwsgi --socket 0.0.0.0:5005 --enable-threads --protocol=http -w wsgi:app
