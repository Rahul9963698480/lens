# XYMP Lens Backend

API-only FastAPI backend for connecting to customer databases, syncing schema metadata, and turning natural-language questions into read-only SQL.

## Architecture

1. **App DB (Supabase Postgres)** — persistent `asyncpg` pool. Stores `projects` and `table_schema_catalog`.
2. **External DB (per project)** — short-lived connectors for schema sync, preview, and SQL execution. Never pooled with the app DB.
3. **SQL agent** — Agno + OpenAI. Reads `table_schema_catalog` to generate SQL. Execution is a separate API call with validation.

Supported external engines: **postgres**, **mongodb**. SQL generation and execution work on **postgres** projects only.

There is no ORM and no Alembic. Schema changes are plain SQL under `supabase/migrations/`, applied with the Supabase CLI.

### Natural language → SQL → table (product flow)

```
User question
    → POST /projects/{id}/sql/generate   (LLM + introspect_schema → SQL text)
    → User reviews / edits SQL in UI
    → POST /projects/{id}/sql/execute    (validate → run on customer DB → table)
```

Generation never connects to the customer database. It only reads `table_schema_catalog` from Supabase. Execution validates SQL first, then opens a short-lived connection to the customer's Postgres.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Set in `.env`:

| Variable | Purpose |
|---|---|
| `SUPABASE_DB_URL` | App DB connection (prefer Supabase pooler URI) |
| `OPENAI_API_KEY` | Required for `/sql/generate` |
| `MODEL_ID` | Optional, defaults to `gpt-4o` |
| `RELATIONSHIP_VERIFY_MODEL_ID` | Optional, cheap model for xlsx relationship verification (defaults to `gpt-4o-mini`) |

`SUPABASE_DB_URL` format (pooler recommended on Windows):

```
postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

Do **not** put anon/service_role API keys here.

### Supabase CLI

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
- `20260806000005_create_table_schema_catalog.sql`
- `20260806000006_add_schema_catalog_annotations.sql`

## Run the API

```bash
uvicorn app.main:app --reload
```

- Health: `GET /health`
- Docs: `http://127.0.0.1:8000/docs`

## Endpoints

### Projects

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/projects` | Create project, test external DB, initial schema sync |
| `GET` | `/projects` | List projects (never includes `db_password`) |
| `DELETE` | `/projects/{project_id}` | Hard delete |
| `GET` | `/projects/{project_id}/preview` | Sample rows from external DB |

Default ports (server-side): `postgres` → `5432`, `mongodb` → `27017`. Clients do not send `db_port`.

### Schema catalog

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/projects/{project_id}/schema/sync` | Re-extract schema into `table_schema_catalog` |
| `GET` | `/projects/{project_id}/schema` | Read stored catalog |
| `PATCH` | `/projects/{project_id}/schema/{table_name}` | Table annotations |
| `PATCH` | `/projects/{project_id}/schema/{table_name}/columns/{column_name}` | Column annotations |

### SQL agent

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/projects/{project_id}/sql/generate` | Natural language → SQL (requires `OPENAI_API_KEY`) |
| `POST` | `/projects/{project_id}/sql/execute` | Run validated read-only SQL on customer Postgres |

#### Generate SQL

```http
POST /projects/{project_id}/sql/generate
Content-Type: application/json

{ "question": "Show top 5 customers by total order amount" }
```

```json
{ "sql": "SELECT ..." }
```

The agent calls `introspect_schema` against `table_schema_catalog` (Supabase only) before writing SQL.

#### Execute SQL

```http
POST /projects/{project_id}/sql/execute
Content-Type: application/json

{ "sql": "SELECT * FROM customer LIMIT 5" }
```

```json
{
  "columns": ["id", "name"],
  "rows": [{ "id": 1, "name": "Alice" }],
  "row_count": 1
}
```

**Execution rules** (`app/db/sql_validation.py`):

- Only `SELECT` / `WITH` queries
- Blocks `INSERT`, `UPDATE`, `DELETE`, `DROP`, and other write/admin keywords
- Single statement only (no `;` chaining)
- 30s statement timeout, max 1000 rows returned
- Postgres projects only

The LLM is not involved in execution. SQL comes only from the request body.

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

URI is built from host + username + password + db_name (`mongodb+srv://` when host looks like Atlas).

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

## Key modules

| Path | Role |
|------|------|
| `app/api/sql_routes.py` | `/sql/generate` and `/sql/execute` endpoints |
| `app/agent/sql_generator.py` | Agno agent — NL to SQL |
| `app/agent/introspect_schema.py` | Reads `table_schema_catalog` (asyncpg) |
| `app/agent/sql_executor.py` | API wrapper for execution |
| `app/db/query_runner.py` | Validates SQL, connects to customer DB, returns rows |
| `app/db/sql_validation.py` | Read-only SQL checks |
| `app/db/connectors/` | External DB adapters (`postgres.py`, `mongodb.py`) |

## Notes

- No frontend in this repo.
- App DB pool and external connectors never share a pool or connection.
- All Postgres I/O uses **asyncpg** (no SQLAlchemy).
- `db_password` is stored in plaintext for now — intentional tradeoff with a TODO to encrypt before production.
