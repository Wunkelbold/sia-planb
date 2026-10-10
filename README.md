# SIA PlanB

SIA PlanB is a Flask application for managing SIA events, shifts, event registrations, tickets, tasks, users, and mail verification.

## Project Layout

- `sia-backend/flask-server`: Flask application, templates, static assets, and migrations.
- `sia-backend/compose.yml`: local development and CI Compose definition.
- `sia-backend/compose.production.yml`: source-free production Compose template.
- `sia-backend/mail-server`: Docker Mailserver configuration and deployment data.
- `sia-backend/test`: smoke-test container used by CI.

## Local Development

Requirements:

- Git
- Docker Desktop or Docker Engine with Compose

Create the local environment file from the tracked template. The resulting `.env` file must never be committed.

```sh
cd sia-backend
cp .env.example .env
docker compose --env-file .env up -d --build
```

The Flask application is available at `http://127.0.0.1:5005`.

Run the smoke tests with:

```sh
docker compose --env-file .env --profile test up --build --abort-on-container-exit --exit-code-from test test
```

The local mail server requires its own hostname and certificate setup. Do not use development certificates or mail accounts in production.

## Configuration

`.env.example` documents the required variables. Each environment needs its own stable values for:

- `SECRET_KEY`
- `CAPTCHA_SECRET_KEY`
- `MAIL_PASSWORD`
- `DATABASE_PASSWORD`

Production secrets must be configured outside Git. Changing `SECRET_KEY` invalidates existing sessions and CSRF tokens.

Python application dependencies are declared in `sia-backend/flask-server/requirements.txt` and locked in `sia-backend/flask-server/requirements.lock`. Update the direct pins, then regenerate the lock with `pip-compile --generate-hashes --output-file requirements.lock requirements.txt` from that directory and build/test the image before deployment.

Before the first deployment of this configuration, add stable production values
for all secret variables and set `APP_ENV=production`. `MAIL_PASSWORD` must match
the password for the existing noreply mailbox. Manage mailbox passwords through
the Docker Mailserver CLI, not from Flask:

```sh
docker exec -it mailserver setup email update noreply@example.com
```

The command prompts for the new password without placing it in shell history.
The Flask container does not mount or modify the mail-account file.

For new deployments, keep persistent mail data outside the source checkout, for example:

```text
MAILSERVER_ENV_FILE=/etc/sia-planb/mailserver.env
MAIL_DATA_PATH=/var/lib/sia-planb/mail/mail-data
MAIL_STATE_PATH=/var/lib/sia-planb/mail/mail-state
MAIL_LOG_PATH=/var/lib/sia-planb/mail/mail-logs
MAIL_CONFIG_PATH=/var/lib/sia-planb/mail/config
```

Production now stores the DMS environment at `/etc/sia-planb/mailserver.env` and mail data/configuration at `/var/lib/sia-planb/mail/`. A pre-move copy remains under the retained server checkout for rollback; do not remove it until the new mounts have been used and verified for the agreed retention period.

## Database Migrations

Migration files live in `sia-backend/flask-server/migrations/versions` and are part of the application source.

Generate a migration during development only after reviewing the model change:

```sh
cd sia-backend
docker compose --env-file .env run --rm migrate \
  flask --app app db revision --autogenerate -m "describe the schema change"
```

Review the generated file and test it against a disposable database. Apply reviewed migrations with:

```sh
docker compose --env-file .env run --rm migrate
```

The web application must not autogenerate migrations at startup. Production migration execution is a single, explicit step before the web container starts.

Never set `DROP_AND_CREATE_DATABASE=true` against a production database.

## Current Deployment

Production uses a copy of `sia-backend/compose.production.yml` at `/etc/sia-planb/compose.yml` and an external environment file at `/etc/sia-planb/production.env`. The production Compose file has no build contexts or test service; CI builds and publishes immutable Flask and database images to GHCR. The server pulls those images and does not need an application checkout. Keep production secrets in the external environment file, never in Git.

Production now runs Flask image `sha-6c7d2b8` on Python 3.14.8/Gunicorn 26.2.0, PostgreSQL 18.6, and Docker Mailserver 16.0.1. The PG17 volume is retained separately as a rollback copy; PostgreSQL 18 uses the new `sia-backend_pgdata18` volume with its version-specific data path. The DMS environment file is at `/etc/sia-planb/mailserver.env` and persistent mail data/configuration is under `/var/lib/sia-planb/mail`. Pre-move copies remain under the server checkout until the rollback retention period expires.

Before a production migration, ensure a recent database backup is available. Keep `DATABASE_IMAGE` pinned to the currently deployed PostgreSQL image; change it only during a separately planned database-image update. For routine application releases, use this sequence:

1. Set `FLASK_IMAGE` in the external environment file to the commit-tagged image published by a successful CI run.
2. Confirm PostgreSQL is already running and healthy.
3. Pull the Flask and migration images, then run the migration job once.
4. Start Flask only after the migration command succeeds.
5. Verify the application healthcheck and smoke-test the site.

Mailbox account changes are handled through Docker Mailserver, separately from Flask. PostgreSQL and the mailserver are not dependencies to restart for an application release; leave their containers and persistent data alone.

```text
FLASK_IMAGE=ghcr.io/wunkelbold/sia-planb/sia-flask:sha-<commit>
```

For a source-free application deployment, install a copy of `sia-backend/compose.production.yml` at `/etc/sia-planb/compose.yml` and maintain its production environment file and persistent-data paths there. Keep the Compose project name `sia-backend` so existing volumes and containers retain their names. Ensure the current PostgreSQL service is already running and healthy, then deploy only Flask and its migration job:

```sh
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env pull flask migrate
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env run --rm --no-deps migrate
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env up -d --no-build --no-deps flask
```

The migration command must exit successfully before the Flask restart command is run. `--no-deps` prevents Compose from restarting PostgreSQL or the mailserver. Keep `DATABASE_IMAGE` pinned so an application release does not upgrade PostgreSQL.

## Full-Stack Version Upgrades

The current PostgreSQL 18.6 image uses `/var/lib/postgresql` and a version-specific data path. PostgreSQL 17 and earlier use `/var/lib/postgresql/data`; an existing PostgreSQL 17 volume must not be attached to the 18 image as though it were already upgraded. The 2026 refresh used a logical dump/restore into a new volume and retained the old volume for rollback. Follow the same separation for future PostgreSQL major upgrades.

Docker Mailserver 16.0.1 moves from Debian 12 to Debian 13 and Dovecot 2.3 to 2.4. The production update was validated against a preserved copy of the mail data before replacing the live image. For future updates, review the release changelog and test with a copy of the mail data; keep the mail paths and account data intact during the image upgrade.

The 2026 refresh used a protected logical database dump, a cold copy of the PG17 volume, and a preserved DMS data/config archive. It validated PostgreSQL 18 restore and DMS 16 startup on copies before separate cutovers, then checked the Alembic head, site health, SMTP/IMAP authentication, account entries, and Maildir message count. Retain the old volume and archives for the agreed rollback period before pruning them.

## Pull Requests

Use a feature branch and open a pull request against `main`. Configure branch protection to require the `CI / Test Code` check before merging. Images are published only after that job succeeds on `main` or a release tag. A pull request should include:

- A description of the behavior change.
- Tests for changed behavior.
- A reviewed migration for schema changes.
- Documentation updates when setup or deployment changes.
- No secrets, personal data, generated logs, mailbox data, or database dumps.

## Backups

Database backups should be stored outside the repository and tested by restoring them to a disposable PostgreSQL instance. A backup that has never been restored is not a verified recovery path.
