# SIA PlanB

React/Vite frontend, Flask API, PostgreSQL, and Docker Mailserver.

## Quick map

```text
Repository
├── frontend/                           React app; build output: frontend/dist/
├── sia-backend/
│   ├── flask-server/Sections/           Flask APIs and application logic
│   ├── flask-server/migrations/versions/ Alembic schema changes
│   ├── flask-server/static/             Frontend media, fonts, and 3D assets
│   ├── database-server/                 PostgreSQL image
│   ├── mail-server/                     Docker Mailserver defaults
│   ├── test/                            Backend smoke suite
│   ├── compose.yml                      Local development and CI
│   ├── compose.production.yml            Source-free production Compose
│   └── .env.example                     Local environment template
├── deployment/backup/                     Offsite backup script and systemd units
├── deployment/nginx/sia-planb.conf       Production nginx site config
└── .github/workflows/build-images.yml    Checks and GHCR image publishing

Production host
├── /etc/sia-planb/compose.yml            Copy of compose.production.yml
├── /etc/sia-planb/production.env         Image tags and production settings/secrets
├── /etc/sia-planb/mailserver.env         Docker Mailserver settings
├── /var/lib/sia-planb/mail/              Live mail data and configuration
├── /var/lib/sia-planb/rollback/          Retained rollback copies
├── /var/www/sia-planb/releases/<sha>/    Deployed React build
├── /var/www/sia-planb/current            Symlink to active frontend release
├── /etc/nginx/sites-available/sia-planb  Copy of deployment/nginx/sia-planb.conf
└── /etc/nginx/sites-enabled/sia-planb    Enabled symlink to sites-available
```

The production host runs published images; it does not need a source checkout. The Flask and database images are published to `ghcr.io/wunkelbold/sia-planb/`. The React build is deployed separately as static files. `deployment/nginx/sia-planb.conf` is host-specific; update its names/certificate paths for another host.

## Local development

Requirements: Docker Compose and Node.js version from `frontend/.nvmrc`.

```sh
cd sia-backend
cp .env.example .env
docker compose --env-file .env up -d --build flask
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies API, static media, calendar feeds, logout, and verification callbacks to Flask at `http://127.0.0.1:5005`.

## Checks

```sh
cd frontend
npm run check
```

Run the backend smoke suite from `sia-backend/`:

```sh
docker compose --env-file .env --profile test up --build --abort-on-container-exit --exit-code-from test test
```

CI runs both checks on pull requests. Successful builds on `main` and `v*` tags publish immutable `sha-<short-sha>` images.

Optional local fixtures, after migrations:

```sh
cd sia-backend
docker compose --env-file .env run --rm -e APP_ENV=development flask flask --app app seed-finance-demo
docker compose --env-file .env run --rm flask flask --app app seed-drink-menu
```

The finance seed is limited to development/test. The drink-menu seed only populates an empty menu.

## Configuration and migrations

- Start from `sia-backend/.env.example`; never commit `.env` or production secrets.
- Store production settings in `/etc/sia-planb/production.env` (root-owned, mode `0600`). Keep `SECRET_KEY` stable; changing it invalidates sessions.
- Keep `DATABASE_IMAGE` pinned during application releases. Change it only as part of a separately planned PostgreSQL upgrade.
- Create and review migrations during development. Production applies them explicitly with the `migrate` Compose service; the web container does not generate migrations.
- Never use `DROP_AND_CREATE_DATABASE=true` against production.

## Production release

Before a migration, confirm a recent database backup and successful CI/image publication. Set the new Flask image and public frontend URL in `/etc/sia-planb/production.env`; leave `DATABASE_IMAGE` unchanged:

```text
FLASK_IMAGE=ghcr.io/wunkelbold/sia-planb/sia-flask:sha-<short-sha>
FRONTEND_URL=https://sia-planb.de
```

Sync `sia-backend/compose.production.yml` to `/etc/sia-planb/compose.yml`. Then, on the production host, run the migration before restarting Flask:

```sh
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env pull flask migrate
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env run --rm --no-deps migrate
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env up -d --no-build --no-deps flask
```

`--no-deps` leaves PostgreSQL and mailserver running. For a new or empty menu, seed once with:

```sh
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env run --rm --no-deps flask flask --app app seed-drink-menu
```

For frontend-only releases (no image pull, no migration), build outside the production host and upload the build from the repository root:

```sh
sha=$(git rev-parse --short HEAD)
npm run build --prefix frontend
scp -r -i <ssh-key> -P 22 frontend/dist root@1.1.1.1:/tmp/sia-planb-dist-$sha
```

Then activate the release on the host:

```sh
sha=<short-sha>   # same value as above
test -f "/tmp/sia-planb-dist-$sha/index.html"
test ! -e "/var/www/sia-planb/releases/$sha"
install -d -m 0755 /var/www/sia-planb/releases   # create releases dir if missing (mode rwxr-xr-x)
mv "/tmp/sia-planb-dist-$sha" "/var/www/sia-planb/releases/$sha"
chmod -R a+rX "/var/www/sia-planb/releases/$sha"
ln -sfn "/var/www/sia-planb/releases/$sha" /var/www/sia-planb/current.next
mv -Tf /var/www/sia-planb/current.next /var/www/sia-planb/current
```

The symlink swap is atomic: nginx serves the previous release until `current` moves. Roll back by repeating the last two commands with the previous release's SHA. The tracked nginx config serves the SPA, proxies API/static/calendar/verification requests to Flask, and preserves the host's status/mail redirects. When it changes, sync it to `/etc/nginx/sites-available/sia-planb`, then run:

```sh
nginx -t && systemctl reload nginx
```

Verify Flask health, the Alembic head, the public site, and `/getraenkekarte`. Retain rollback copies under `/var/lib/sia-planb/rollback/` for the agreed retention period. PostgreSQL major-version and Docker Mailserver upgrades require separate plans and tested backups.

## Mail anti-spam

The mailserver runs Rspamd (the legacy OpenDKIM/OpenDMARC/policyd-spf stack is disabled) with an internal Redis instance for greylisting and statistics. Outbound DKIM keeps the existing selector `mail`; the key and Rspamd overrides live in the mail config volume (`/var/lib/sia-planb/mail/config/rspamd/`) and are required for signing. Do not delete them.

A small recursive DNS resolver (`dns-recursor`, PowerDNS Recursor, pinned in `compose.production.yml`) runs alongside the mailserver on a dedicated Docker network and is used only by it. Blocklist providers refuse queries from public/shared resolvers, so RBL/DNSBL checks only work through a local recursor. The service is never published outside the Compose network and is reached by the mailserver at a fixed address.

Live behavior: `docker exec mailserver tail -f /var/log/mail/rspamd.log`; manual scans with `docker exec mailserver rspamc < message.eml`. The Rspamd web controller (port 11334) is not published; use an SSH/Docker tunnel if needed. Bayes learning and MTA-STS are deliberately not enabled yet.

## Backups

Production state is backed up once a day by a host-side script plus systemd timer, stored encrypted and deduplicated offsite with [restic](https://restic.net/), and monitored with an Uptime Kuma push monitor. The files live in `deployment/backup/`; no backup data is ever committed to this repository, including database dumps.

Each run backs up:

- `pg_dump --format=custom` of the application database plus `pg_dumpall --globals-only` for roles
- Mail data, mail config, and Rspamd/Redis state (`MAIL_DATA_PATH`, `MAIL_CONFIG_PATH`, `MAIL_STATE_PATH/lib-redis`)
- Uploaded images (Docker volumes `eventposter`, `drinkimages`)
- `/etc/sia-planb` (compose file and env files; `backup.env` and the restic password are excluded)

Retention is 7 daily, 5 weekly, and 12 monthly snapshots. Recommended offsite target: a Backblaze B2 bucket (10 GB free, then $6/TB/month, no minimum) or a second server over SFTP. Restic only stores unique data, so the repository stays roughly the size of the mail store plus uploads.

One-time setup on the production host:

```sh
# restic: install the official static binary (the production host runs an EOL
# Debian release where apt no longer provides packages)
ver=0.19.1
curl -fsSL -o /tmp/restic.bz2 "https://github.com/restic/restic/releases/download/v${ver}/restic_${ver}_linux_amd64.bz2"
bzip2 -dc /tmp/restic.bz2 > /usr/local/bin/restic && chmod 0755 /usr/local/bin/restic && rm /tmp/restic.bz2
install -m 0600 deployment/backup/backup.env.example /etc/sia-planb/backup.env   # edit repository/credentials
install -m 0600 /dev/null /etc/sia-planb/restic-password                        # put a strong password inside
install -m 0755 deployment/backup/backup.sh /usr/local/bin/sia-planb-backup.sh
install -m 0644 deployment/backup/sia-planb-backup.service deployment/backup/sia-planb-backup.timer /etc/systemd/system/
set -a; . /etc/sia-planb/backup.env; set +a; restic init
systemctl daemon-reload && systemctl enable --now sia-planb-backup.timer
```

Then create an Uptime Kuma push monitor (heartbeat slightly above 24h) and paste its URL into `KUMA_PUSH_URL`. The script reports success, failure, and run duration, so a missing or failing backup alerts without extra supervision. Keep a copy of `/etc/sia-planb/backup.env` and the restic password in the club password manager - without the password, no backup can be restored. Run a first backup manually with `systemctl start sia-planb-backup.service` and watch it with `journalctl -u sia-planb-backup.service -f`.

Restore (verify first, then replace live data while Flask is stopped):

```sh
restic snapshots
restic restore latest --target /tmp/sia-planb-restore
# Verify the database dump against a scratch database before touching live data:
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env exec -T database createdb -U postgres restorecheck
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env exec -T database pg_restore -U postgres -d restorecheck < /tmp/sia-planb-restore/var/lib/sia-planb/backups/staging/database.dump
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env exec -T database dropdb -U postgres restorecheck
# Mail: stop the mailserver, copy the restored files into MAIL_DATA_PATH and
# MAIL_CONFIG_PATH, then start it again.
```

A backup that has never been restored is not a verified recovery path; run a restore drill at least once per release cycle.
