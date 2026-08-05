# Glamira API

FastAPI + PostgreSQL backend for the Glamira app. Currently implements
authentication for the existing app screens (login, signup, forgot password).

## Stack
- FastAPI + Uvicorn
- PostgreSQL via async SQLAlchemy 2.0 + asyncpg
- JWT auth (PyJWT), bcrypt password hashing

## Setup

```bash
cd ~/Desktop/glamira-backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then edit DATABASE_URL / SECRET_KEY
createdb glamira              # or: psql -c "CREATE DATABASE glamira;"
.venv/bin/alembic upgrade head   # create the schema
```

> Upgrading an existing DB that predates Alembic (its tables were created by the
> old startup `create_all`)? Run `alembic stamp head` **once** instead of
> `upgrade` to record the current revision without re-creating tables.

`.env` `DATABASE_URL` uses the async driver, e.g.:
```
postgresql+asyncpg://<user>:<password>@localhost:5432/glamira
```

## Run

```bash
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Interactive docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Migrations (Alembic)

The schema is managed by Alembic — the app no longer creates tables at startup.

```bash
.venv/bin/alembic upgrade head                       # apply migrations
.venv/bin/alembic revision --autogenerate -m "msg"   # after changing models.py
.venv/bin/alembic downgrade -1                        # roll back one revision
.venv/bin/alembic current                             # show current revision
```

Alembic reads `DATABASE_URL` from your `.env` (via `app.config`), so it always
targets the same database as the app.

## Deploy (Render, free tier)

`render.yaml` is a Render Blueprint that provisions the API + a free PostgreSQL
database. Push to GitHub, then in Render: **New +** → **Blueprint** → pick this
repo. Migrations run automatically on each deploy (`alembic upgrade head` is
prepended to the start command).

Free-tier caveats: the web service sleeps after ~15 min idle (slow first
request), the filesystem is ephemeral so uploaded avatars in `media/` are wiped
on redeploy (use object storage for real persistence), and the free database is
removed ~90 days after creation.

## Endpoints

| Method | Path                    | Purpose                              |
|--------|-------------------------|--------------------------------------|
| POST   | `/auth/signup`          | Create account → `{access_token, user}` |
| POST   | `/auth/login`           | Email + password → `{access_token, user}` |
| POST   | `/auth/forgot-password` | Email a reset link (always 200)      |
| POST   | `/auth/reset-password`  | `{token, new_password}`              |
| GET    | `/auth/me`              | Current user (Bearer token)          |

When SMTP isn't configured, the password-reset link is **logged to the server
console** instead of emailed — handy for local testing.

## Notes / next steps
- Google sign-in: add a `/auth/google` endpoint that verifies a Google ID token
  (needs `google-auth` + a Google OAuth client id).
- Add Alembic for migrations before deploying.
