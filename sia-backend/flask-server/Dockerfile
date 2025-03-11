# syntax=docker/dockerfile:1

FROM ghcr.io/wunkelbold/sia-planb/sia-flask:latest

WORKDIR /opt/flask-backend
COPY . /opt/flask-backend


RUN pip install -r requirements.txt
RUN apt-get update && apt-get install -y dovecot-core
RUN apt-get install -y locales && sed -i '/de_DE.UTF-8/s/^# //g' /etc/locale.gen && locale-gen locale-gen de_DE.UTF-8 

CMD uwsgi --socket 0.0.0.0:80 --enable-threads --protocol=http -w app:app --stats 0.0.0.0:9191 --stats-http --workers 4 --threads 2
