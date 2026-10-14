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

Build the frontend outside the production host with `npm run build --prefix frontend`. Transfer `frontend/dist/` to a new `/var/www/sia-planb/releases/<sha>/`, then atomically point `current` at that release. The tracked nginx config serves the SPA, proxies API/static/calendar/verification requests to Flask, and preserves the host's status/mail redirects. When it changes, sync it to `/etc/nginx/sites-available/sia-planb`, then run:

```sh
nginx -t && systemctl reload nginx
```

Verify Flask health, the Alembic head, the public site, and `/getraenkekarte`. Retain rollback copies under `/var/lib/sia-planb/rollback/` for the agreed retention period. PostgreSQL major-version and Docker Mailserver upgrades require separate plans and tested backups.
