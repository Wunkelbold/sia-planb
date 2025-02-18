For Mailserver-development:

mkdir -p /etc/ssl/mailserver
openssl req -x509 -newkey rsa:4096 -keyout /etc/ssl/mailserver/mailserver.key -out /etc/ssl/mailserver/mailserver.crt -days 365 -nodes
