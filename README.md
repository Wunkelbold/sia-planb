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

Production mail paths should point outside the Git checkout, for example:

```text
MAILSERVER_ENV_FILE=/etc/sia-planb/mailserver.env
MAIL_ACCOUNTS_FILE_HOST=/var/lib/sia-planb/mail/config/postfix-accounts.cf
MAIL_DATA_PATH=/var/lib/sia-planb/mail/mail-data
MAIL_STATE_PATH=/var/lib/sia-planb/mail/mail-state
MAIL_LOG_PATH=/var/lib/sia-planb/mail/mail-logs
MAIL_CONFIG_PATH=/var/lib/sia-planb/mail/config
```

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

The current production deployment is a server-side Compose build. It uses persistent PostgreSQL and mail volumes and keeps some environment and mail state outside Git.

The deployment script must always:

1. Create a verified database backup.
2. Build or pull the intended application version.
3. Run `flask db upgrade` once.
4. Start the web service only if the migration succeeds.
5. Verify the healthcheck and smoke tests.

The planned deployment pipeline builds the complete Flask application image in CI, publishes it with an immutable commit tag, and lets the operator pull that tag manually on the server. The server will not need to clone the application source.

After the image workflow has published a version, set the Flask image tag in the external production environment file. Keep `DATABASE_IMAGE` pinned to the currently deployed PostgreSQL image; change it only during a separately planned database-image update.

```text
FLASK_IMAGE=ghcr.io/wunkelbold/sia-planb/sia-flask:sha-<commit>
```

For a source-free application deployment, install a copy of `sia-backend/compose.yml` at `/etc/sia-planb/compose.yml` and maintain its production environment file and persistent-data paths there. Keep the Compose project name `sia-backend` so existing volumes and containers retain their names. Ensure the PostgreSQL service is already running, then deploy only Flask and its migration job:

```sh
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env pull flask migrate
docker compose --project-name sia-backend --file /etc/sia-planb/compose.yml --env-file /etc/sia-planb/production.env up -d --no-build flask
```

These commands pull and replace only the Flask application image. Targeting `flask` starts its database and one-shot migration dependencies, and Flask starts only if the migration succeeds. The mailserver is not a dependency and is not pulled or restarted. Keep `DATABASE_IMAGE` pinned to the currently deployed database image so an application release does not upgrade PostgreSQL.

## Pull Requests

Use a feature branch and open a pull request against `main`. Configure branch protection to require the `CI / Test Code` check before merging. Images are published only after that job succeeds on `main` or a release tag. A pull request should include:

- A description of the behavior change.
- Tests for changed behavior.
- A reviewed migration for schema changes.
- Documentation updates when setup or deployment changes.
- No secrets, personal data, generated logs, mailbox data, or database dumps.

## Backups

Database backups should be stored outside the repository and tested by restoring them to a disposable PostgreSQL instance. A backup that has never been restored is not a verified recovery path.
