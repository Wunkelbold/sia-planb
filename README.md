# SIA PlanB

SIA PlanB is a Flask application for managing SIA events, shifts, event registrations, tickets, tasks, users, and mail verification.

## Project Layout

- `sia-backend/flask-server`: Flask application, templates, static assets, and migrations.
- `sia-backend/compose.yml`: local and current server Compose definition.
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

Before the first deployment of this configuration, add stable production values
for all secret variables and set `APP_ENV=production`. The existing generated
noreply mailbox password must be replaced with the configured `MAIL_PASSWORD`.
Use `UPDATE_MAIL_USER=true` for one controlled mailbox provisioning step, then
set it back to `false` for normal application starts.

For new deployments, keep persistent mail data outside the source checkout, for example:

```text
MAILSERVER_ENV_FILE=/etc/sia-planb/mailserver.env
MAIL_ACCOUNTS_FILE_HOST=/var/lib/sia-planb/mail/config/postfix-accounts.cf
MAIL_DATA_PATH=/var/lib/sia-planb/mail/mail-data
MAIL_STATE_PATH=/var/lib/sia-planb/mail/mail-state
MAIL_LOG_PATH=/var/lib/sia-planb/mail/mail-logs
MAIL_CONFIG_PATH=/var/lib/sia-planb/mail/config
```

The existing production mail data still uses its established paths under the retained server checkout. Application image deployments must leave those paths unchanged; moving mail data is a separate migration that needs its own backup and verification.

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

Production uses an external Compose file at `/etc/sia-planb/compose.yml` and environment file at `/etc/sia-planb/production.env`. CI builds and publishes the Flask image to GHCR with an immutable commit tag; the server pulls that image and does not need to build or pull application source. Keep production secrets in the external environment file, never in Git.

Before a production migration, ensure a recent database backup is available. Keep `DATABASE_IMAGE` pinned to the currently deployed PostgreSQL image; change it only during a separately planned database-image update. For routine application releases, use this sequence:

1. Set `FLASK_IMAGE` in the external environment file to the commit-tagged image published by a successful CI run.
2. Confirm PostgreSQL is already running and healthy.
3. Pull the Flask and migration images, then run the migration job once.
4. Start Flask only after the migration command succeeds.
5. Verify the application healthcheck and smoke-test the site.

`UPDATE_MAIL_USER` must remain `false` during normal deployments. PostgreSQL and the mailserver are not dependencies to restart for an application release; leave their containers and persistent data alone.

```text
FLASK_IMAGE=ghcr.io/wunkelbold/sia-planb/sia-flask:sha-<commit>
```

For a source-free application deployment, install a copy of `sia-backend/compose.yml` at `/etc/sia-planb/compose.yml` and maintain its production environment file and persistent-data paths there. Keep the Compose project name `sia-backend` so existing volumes and containers retain their names. Ensure the current PostgreSQL service is already running and healthy, then deploy only Flask and its migration job:

```sh
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env pull flask migrate
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env run --rm --no-deps migrate
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env up -d --no-build --no-deps flask
```

The migration command must exit successfully before the Flask restart command is run. `--no-deps` prevents Compose from restarting PostgreSQL or the mailserver. Keep `DATABASE_IMAGE` pinned so an application release does not upgrade PostgreSQL.

## Pull Requests

Use a feature branch and open a pull request against `main`. Configure branch protection to require the `CI / Test Code` check before merging. Images are published only after that job succeeds on `main` or a release tag. A pull request should include:

- A description of the behavior change.
- Tests for changed behavior.
- A reviewed migration for schema changes.
- Documentation updates when setup or deployment changes.
- No secrets, personal data, generated logs, mailbox data, or database dumps.

## Backups

Database backups should be stored outside the repository and tested by restoring them to a disposable PostgreSQL instance. A backup that has never been restored is not a verified recovery path.
