For Mailserver-development:
docker pull ghcr.io/wunkelbold/sia-planb/sia-flask:latest
docker pull ghcr.io/wunkelbold/sia-planb/sia-database:latest
docker pull ghcr.io/docker-mailserver/docker-mailserver

mkdir -p /etc/ssl/mailserver
openssl req -x509 -newkey rsa:4096 -keyout /etc/ssl/mailserver/mailserver.key -out /etc/ssl/mailserver/mailserver.crt -days 365 -nodes
