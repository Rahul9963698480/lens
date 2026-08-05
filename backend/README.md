# XYMP Lens Backend

API-only FastAPI backend with two separate connection paths:

1. **App DB (Supabase Postgres)** — persistent `asyncpg` pool. Stores only `projects`.
2. **External DB (per project)** — short-lived connectors via an adapter layer. Never pooled with the app DB.

Supported external engines today: **postgres**, **mongodb**. Adding MySQL/SQLite later means one new file under `app/db/connectors/`.

There is no ORM and no Alembic. Schema changes are plain SQL under `supabase/migrations/`, applied with the Supabase CLI.

## Setup

```bash
conda create -n xymp_lens_backend python=3.12 -y
conda activate xymp_lens_backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set SUPABASE_DB_URL (prefer the pooler URI from Supabase → Settings → Database)
```

`SUPABASE_DB_URL` format (pooler recommended on Windows):

```
postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

Do **not** put anon/service_role API keys here.

### Supabase CLI

Install from GitHub releases (`%LOCALAPPDATA%\supabase-cli` on this machine). Verify:

```bash
supabase --version
```

## Migrations

```bash
# Option A — link once, then push
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase db push

# Option B — push with an explicit DB URL (pooler URI from .env)
supabase db push --db-url "%SUPABASE_DB_URL%"
```

Current migrations:

- `20260803000001_create_users_table.sql`
- `20260803000002_create_projects_table.sql`
- `20260803000003_add_projects_engine.sql`
- `20260803000004_drop_users_and_project_user_id.sql`

## Run the API

```bash
conda activate xymp_lens_backend
uvicorn app.main:app --reload
```

- Health: `GET /health`
- Docs: `http://127.0.0.1:8000/docs`

## Endpoints

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/projects` | Requires `engine`; port inferred from engine; tests external DB first; `400` `{ "error": "..." }` on failure |
| `GET` | `/projects` | List projects (never includes `db_password`) |
| `DELETE` | `/projects/{project_id}` | Hard delete |
| `GET` | `/projects/{project_id}/preview` | Sample tables/collections from the external DB |

Default ports (server-side): `postgres` → `5432`, `mongodb` → `27017`. Clients do not send `db_port`.

### Example: create a Postgres project

```json
{
  "name": "My Postgres",
  "engine": "postgres",
  "db_host": "db.example.com",
  "db_name": "mydb",
  "db_username": "user",
  "db_password": "secret"
}
```

### Example: create a MongoDB Atlas project

URI is built from host + username + password + db_name (`mongodb+srv://` when host looks like Atlas). No raw connection-string field.

```json
{
  "name": "Sample Mflix",
  "engine": "mongodb",
  "db_host": "cluster0.xxxxx.mongodb.net",
  "db_name": "sample_mflix",
  "db_username": "my_user",
  "db_password": "secret"
}
```

Preview response shape is engine-agnostic: `{ project_id, tables: [{ table_name, columns, rows | error }] }` (Mongo collections appear as `table_name`).

`db_password` is stored in plaintext for now — intentional tradeoff with a TODO to encrypt before production.

## Notes

- No frontend in this repo.
- App DB pool and external connectors never share a pool or connection.
- Connector adapters live in `app/db/connectors/` (`base.py`, `factory.py`, `postgres.py`, `mongodb.py`).
