# Contributing

## Workflow

1. Create a feature branch from `main`.
2. Make the smallest coherent change.
3. Add or update tests and documentation.
4. Run the Compose smoke tests locally.
5. Open a pull request and wait for CI before merging.

Do not commit `.env` files, passwords, private keys, mailbox data, database dumps, logs, or generated migration files created by a production process.

## Schema Changes

Create migrations during development, review the generated SQL operations, and test both upgrade and downgrade behavior where downgrade is supported. Never generate migrations from a production web-process startup.

## Deployment Changes

Deployment changes must document:

- Required environment variables.
- Whether a database migration is required.
- Whether persistent volumes or mail configuration change.
- How to verify the deployment.
- How to roll back.
