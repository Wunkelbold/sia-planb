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
- Node.js 24.21.0 for the static frontend (`frontend/.nvmrc`)

Create the local environment file from the tracked template. The resulting `.env` file must never be committed.

```sh
cd sia-backend
cp .env.example .env
docker compose --env-file .env up -d --build flask
```

This starts PostgreSQL, the one-off migration job, and Flask. The legacy Flask site is available at `http://127.0.0.1:5005`. The example `FRONTEND_URL` points verification and password-reset emails at the local React server (`http://127.0.0.1:5173`).

In a second terminal, run the frontend development server:

```sh
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The React app includes `/` home, `/events`, `/verein`, `/location`, `/contact`, `/datenschutz`, and `/impressum`. Vite proxies `/api/*`, `/static/*`, logout, verification callbacks, and public/personal calendar feeds to the local Flask service, so browser requests use the same-origin development server without CORS configuration. Login, registration, and password recovery (`/forgot-password`, `/reset-password`) are React pages backed by Flask's session, form validation, and signed, expiring email links. Contact requests retain CAPTCHA, privacy consent, and optional anonymous feedback. Event details and participation options use `/api/v1/events/<id>`. Signed-in users can review registrations at `/me/registrations`, manage shifts/tasks at `/me/commitments`, manage their profile at `/me/profile`, and use the member finance page at `/me/finances`. Finance membership is separate from account roles; active members can record their own tally purchases through the QR-linked page, while annual dues, cycle-specific student-email checks, charges, account-level payments, and payment history are tracked separately. The first-year-free student/alumni fee rates are configurable; unverified student eligibility uses the alumni rate for that cycle. Admins manage active memberships, requests, rates, tally products, March billing runs, payments, item status, and manual reminders in the Finanzen tab at `/admin`. The initial Glasflaschen/Longdrinks products have no price and must be configured before members can use them; reminders require payment instructions to be set in the admin panel. Admin Users is a scrollable list sorted by most recent login, Tasks is a cross-event overview sortable by due date or priority, and Events embeds the organizer workflow. Authorized organizers can manage events at `/manage/events`, event tasks at `/manage/events/<id>/tasks`, and scan tickets at `/scanner`; attendees view and join tasks at `/events/<id>/tasks`. Flask filters results by event/task visibility, and signed-in changes use the session CSRF token.

The Admin Finanzen view lets administrators directly assign or change a member's fee category with an audit note, without waiting for a member request. It also provides one bulk action per member to mark all currently open drink-tally entries as paid. This status action is audited and does not change the account balance; recorded account payments change the balance, and cancelled charges reverse it.

Annual dues billing runs are numbered per cycle. An admin can void an issued run with a reason; its charges are archived as cancelled, the run remains in history, and a replacement run can then be issued for the same year.

Event managers can add or remove eligible users from registration options, helper shifts, and task assignments. Eligibility is checked against both event visibility and the target registration/task permissions (and `events.help` for shifts); assignments do not change a user's role. Sia-Alumni remains a self-selected role with its existing public permissions.

Priced event registrations create user-owned ticket charges in the shared finance account ledger without creating a Finance membership or annual dues. Ticket prices are snapshotted at registration; the manual paid status is shared with the scanner, and recording a payment does not change it automatically. Legacy registrations without a linked charge remain available in the Eventtickets reconciliation view; they are never silently imported or marked paid.

Tally access is based on the app's `Mitglied` or `Moderator` role (and Admin permissions), not on an active Beitragsmitgliedschaft. Members and Moderators can use Tally without a Beitragsmitgliedschaft; Guests and Sia-Alumni do not see the Tally interface. A Beitragsmitgliedschaft request is specifically a request to enter the dues cycle. The `Mitglied` app role is requestable and reviewed by an Admin; `Moderator` and `Admin` are assigned by administrators. Public roles remain self-selectable, including Sia-Alumni, so users can always downgrade to a public role from their profile.

The user Finance view and Admin account ledger combine membership, Tally, and event-ticket charges against the user balance. Marking a charge paid remains a manual reconciliation action; recording a payment credits the account but does not assign it to or mark individual charges. The annual incoming-payment and open-balance audit overview is planned as a separate follow-up.

Frontend checks:

```sh
cd frontend
npm run check
npm run build
```

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

## Finance Demo Data

The current finance behavior supersedes the older overview text above: alumni map to the €50 full rate; the reduced, student, vocational-training, and exempt rates are €25, €20, €20, and €0. Verified students are exempt through their joining semester and then billed 9/12 in March or 3/12 in September for their first contribution year. Existing annual categories are billed in March; full/rate-category new members are charged within six weeks. Overpayments remain account credit and are used against later charges.

For local development, after the database migrations have completed, create demo member accounts and finance records with:

```powershell
$env:APP_ENV = "development"
docker compose --env-file .env run --rm -e APP_ENV=development flask flask --app app seed-finance-demo
```

The command refuses to run in production, does not delete existing data, and is idempotent for its `demo...` accounts. Newly created accounts share the password `TestFinance2026!` by default; override it with `--password`. The seed covers winter/summer student proration, annual PDF categories, a student-to-full-rate midyear change, partial payments, prepayment credit, and a payment ready for storno testing.

## Drink Menu

The public drink menu is available at `/getraenkekarte` and is linked as "Getränke" in the main navigation. It shows only active categories and items, hides prices per item or per category when configured, and renders uploaded pictures or logos. The QR code on the page always points to the live menu URL, so printed copies stay up to date.

Admins with the `menu.manage` permission (the Admin role has it) manage the menu under **Admintool → Getränkekarte**: create categories with optional subtitle and price, add items with name, group, volume, description, price visibility, sort order, and an uploaded image (PNG/JPG/WebP, max 5 MB, downscaled automatically). Deactivating an item or category hides it without deleting history.

The QR code encodes `FRONTEND_URL` plus `/getraenkekarte`; set `FRONTEND_URL` in every deployment so scanned codes open the public site instead of the API host.

For local development, after the database migrations have completed, create the printed menu once with:

```powershell
docker compose --env-file .env run --rm -e APP_ENV=development flask flask --app app seed-drink-menu
```

The command only runs when no categories exist yet and never overwrites edited data. Uploaded drink images are stored in the `drinkimages` volume alongside the existing `eventposter` volume.
