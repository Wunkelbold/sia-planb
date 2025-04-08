docker pull ghcr.io/wunkelbold/sia-planb/sia-flask:latest
docker pull ghcr.io/wunkelbold/sia-planb/sia-database:latest
docker pull ghcr.io/docker-mailserver/docker-mailserver

# Develop Mailserver locally
/etc/hosts 
127.0.0.1 localtest.me
# Selfsigned
mkdir -p /etc/ssl/mailserver
openssl req -x509 -newkey rsa:4096 -keyout /etc/ssl/mailserver/mailserver.key -out /etc/ssl/mailserver/mailserver.crt -days 365 -nodes

Mail anlegen:
~$ docker exec -it mailserver setup email add test@example.com mypassword
oder
~$ echo "test@example.com|$(doveadm pw -s SHA512-CRYPT -p mypassword)" >> ./config/postfix-accounts.cf

localeset package:
~$ locale-gen de_DE.UTF-8

ALTER TABLE events ALTER COLUMN author SET DEFAULT 1;
ALTER TABLE task ALTER COLUMN authorFK SET DEFAULT 1;



