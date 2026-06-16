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
```

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

Tables are auto-created on startup (dev convenience). For production, replace
`init_db()` with Alembic migrations.

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
