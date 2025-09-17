# syntax=docker/dockerfile:1

FROM docker.io/python:3.11

COPY sia-backend/server/requirements.txt /tmp/requirements.txt
RUN apt-get update -y && \
    apt-get install -y postgresql && \
    pip install -r /tmp/requirements.txt
