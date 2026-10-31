> **Example only** — a real SKILL.md for DB migrations. Copy to `.github/skills/run-db-migrations/SKILL.md` to use.

```markdown
---
name: run-db-migrations
description: 'Run database migrations and seed data. Use when: migrating schema, rolling back, seeding test data, resetting local database.'
user-invocable: true
---

# Database Migrations

Manage database schema migrations and seed data.

## When to Use
- Applying new migrations during development
- Rolling back a bad migration
- Resetting and re-seeding the local database
- Setting up a fresh database for a new contributor

## Prerequisites
- Database running locally (Docker: `docker compose up -d db`)
- Migration tool installed (Alembic, Prisma, Flyway, etc.)

## Procedure
1. **Check status** — `alembic current` (or equivalent) to see current migration.
2. **Run pending migrations** — `alembic upgrade head`
3. **Seed data** — `python scripts/seed.py`
4. **Verify** — Run `python scripts/verify-data.py` or check via CLI query.

## Rollback
```bash
alembic downgrade -1   # roll back one step
alembic downgrade <revision>  # roll back to specific revision
```

## Troubleshooting
- **Migration fails**: Check `DATABASE_URL` env var is set.
- **Conflict with existing data**: Run `alembic stamp head` if the schema is already up to date.
- **Reset everything**: `alembic downgrade base && alembic upgrade head && python scripts/seed.py`
```
