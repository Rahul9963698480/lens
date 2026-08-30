# XYMP Lens Backend

API-only FastAPI backend for connecting to customer databases, syncing schema metadata, and turning natural-language questions into read-only SQL.

## Architecture

1. **App DB (Supabase Postgres)** — persistent `asyncpg` pool. Stores `projects`, `table_schema_catalog`, query attempts / learnings, and playground chats (`playground_conversations`, `playground_messages`).
2. **External DB (per project)** — short-lived connectors for schema sync, preview, and SQL execution. Never pooled with the app DB.
3. **Agents (Agno + OpenAI)** — schema introspect + SQL generation. The backend executes SQL; the LLM has no execute tool.

Supported engines: **postgres**, **mongodb** (schema/preview), **xlsx** (Excel → DuckDB). SQL generate/execute and Playground analysis run on **postgres** and **xlsx**.

There is no ORM and no Alembic. Schema changes are plain SQL under `supabase/migrations/`, applied with the Supabase CLI.

### Playground (what the UI uses)

The frontend Playground does **not** call `/sql/generate`. It uses the analysis endpoints:

```
User question
    → POST /projects/{id}/analysis/start     (propose SQL; confirm in UI)
    → POST /projects/{id}/analysis/{id}/run  (execute SQL + analysis answer)
```

Follow-up questions in the same chat inject the last N turns as **question + SQL + analysis answer** only. Result tables and graph config are stored for the Data/Query/Graph tabs but are **not** sent back to the LLM.

Chat memory is `format_conversation_history` in `app/agent/analysis_agent.py` plus rows in `playground_messages`. Agno session summaries / `add_history_to_context` / `num_history_runs` are **not** used across questions. `/run` still uses in-memory Agno history only inside that one request (so introspect can be reused while synthesizing).

To change how many past turns go into the prompt, edit `limit=` on `list_recent_turns` in `app/api/analysis_routes.py` (keep the default in `app/db/conversations.py` in sync).

### Natural language → SQL → table (standalone SQL API)

```
User question
    → POST /projects/{id}/sql/generate   (LLM + introspect_schema → SQL text)
    → User reviews / edits SQL
    → POST /projects/{id}/sql/execute    (validate → run on customer DB or DuckDB → table)
```

Generation never connects to the customer database. It only reads `table_schema_catalog` from Supabase. Execution validates SQL first, then opens a short-lived connection (Postgres) or DuckDB (xlsx).

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
| `OPENAI_API_KEY` | Required for `/sql/generate` and Playground `/analysis/*` |
| `MODEL_ID` | Optional, defaults to `gpt-4o` |
| `XLSX_INGEST_CHUNK_SIZE` | Optional, Excel ingest batch size (default 3000) |
| `DUCKDB_MEMORY_LIMIT` | Optional, DuckDB RAM cap (default `1GB`) |
| `DUCKDB_THREADS` | Optional, DuckDB worker threads (default 4) |

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
- `20260818000007_create_query_attempts_and_confirmed_learnings.sql`
- `20260819000008_xlsx_projects.sql`
- `20260825000009_add_query_attempts_analysis_id.sql`
- `20260830000010_playground_conversations.sql`

Apply `20260830000010` before using Playground chats (`playground_conversations`, `playground_messages`). Messages cascade when a conversation is deleted.

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
| `POST` | `/projects` | Create Postgres/Mongo project, test external DB, initial schema sync |
| `POST` | `/projects/upload-xlsx` | Multipart: `name` + `.xlsx` file. Ingest to DuckDB, store file in Supabase Storage, catalog schema |
| `GET` | `/projects` | List projects (never includes `db_password`) |
| `DELETE` | `/projects/{project_id}` | Hard delete (xlsx cache/file cleanup) |
| `GET` | `/projects/{project_id}/preview` | Sample rows (Postgres/Mongo or DuckDB for xlsx) |
| `GET` | `/health` | `{ "status": "ok" }` |

Default ports (server-side): `postgres` → `5432`, `mongodb` → `27017`. Clients do not send `db_port`.

### Schema catalog

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/projects/{project_id}/schema/sync` | Re-extract schema into `table_schema_catalog` |
| `GET` | `/projects/{project_id}/schema` | Read stored catalog |
| `PATCH` | `/projects/{project_id}/schema/{table_name}` | Table annotations |
| `PATCH` | `/projects/{project_id}/schema/{table_name}/columns/{column_name}` | Column annotations |

### Playground analysis

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/projects/{project_id}/analysis/start` | Body: `{ "question", "conversation_id"? }`. Creates a chat if `conversation_id` is omitted. Injects last-N Q/SQL/answer. Returns proposed SQL to confirm. |
| `POST` | `/projects/{project_id}/analysis/{analysis_id}/run` | Executes confirmed SQL (postgres or DuckDB). Query `stream=1` for SSE progress. Query `conversation_id` to persist the turn after success. |

```http
POST /projects/{project_id}/analysis/start
Content-Type: application/json

{ "question": "lastname of customer Akash", "conversation_id": null }
```

```json
{
  "analysis_id": "...",
  "attempt_id": "...",
  "conversation_id": "...",
  "proposed_sql": "SELECT ...",
  "message": "Running this analysis requires executing queries against your data. Proceed?"
}
```

```http
POST /projects/{project_id}/analysis/{analysis_id}/run?stream=1&conversation_id={conversation_id}
```

Happy path on `/run`: execute at most two queries, then one synthesize LLM call. Result previews are capped for the agent; the Data tab can still restore `queries_used` from the saved message.

**Analysis layer** (`app/agent/analysis_agent.py`):

- Agent has **no** `execute_query` tool. Backend runs SQL via `execute_sql_for_project`.
- `/start` proposes SQL (JSON `run_query`). `/run` executes, then synthesizes a bullet-style answer (no markdown tables — those belong in the Data tab).
- Learnings (`confirmed_learnings`) are loaded **once** per `/run` and also used on `/start`.
- xlsx SQL uses DuckDB dialect; Postgres uses asyncpg.

### Learnings (feedback)

Correct/incorrect SQL feedback becomes reusable rules for later generate/analysis.

| Method | Path | Notes |
|--------|------|--------|
| `PATCH` | `/projects/{project_id}/attempts/{attempt_id}/feedback` | Body: `{ "feedback": "correct" \| "incorrect" }` |
| `POST` | `/projects/{project_id}/attempts/{attempt_id}/confirm` | Body: `{ "confirmed_sql", "rule_text" }` → insert `confirmed_learnings` |

### Playground conversations

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/projects/{project_id}/conversations` | List chats for the left sidebar |
| `GET` | `/projects/{project_id}/conversations/{conversation_id}` | Full thread (Q/SQL/answer + `queries_used` for UI restore) |
| `DELETE` | `/projects/{project_id}/conversations/{conversation_id}` | Delete chat and its messages (204) |

### SQL agent

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/projects/{project_id}/sql/generate` | Natural language → SQL (requires `OPENAI_API_KEY`) |
| `POST` | `/projects/{project_id}/sql/execute` | Run validated read-only SQL on customer Postgres or DuckDB (xlsx) |

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
- 30s statement timeout; execute API max 1000 rows; analysis execute uses a tighter row cap for the LLM
- Postgres and xlsx (DuckDB) projects

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

### Excel → DuckDB

`POST /projects/upload-xlsx` streams sheets into DuckDB, infers types/relationships (`RELATIONSHIP_VERIFY_MODEL_ID`), writes catalog rows, and stores the workbook in Supabase Storage. Later SQL (Playground `/run` or `/sql/execute`) runs **on that DuckDB file**, not on customer Postgres.

Env: `XLSX_INGEST_CHUNK_SIZE`, `DUCKDB_MEMORY_LIMIT`, `DUCKDB_THREADS`. Requires `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`.

## Key modules

| Path | Role |
|------|------|
| `app/api/analysis_routes.py` | Playground `/analysis/start` and `/run` |
| `app/api/conversation_routes.py` | List / get / delete playground chats |
| `app/db/conversations.py` | `playground_conversations` and `playground_messages` |
| `app/agent/analysis_agent.py` | Propose SQL or synthesize answers; `format_conversation_history` |
| `app/api/sql_routes.py` | `/sql/generate` and `/sql/execute` endpoints |
| `app/agent/sql_generator.py` | Agno agent — NL to SQL (standalone SQL API) |
| `app/agent/introspect_schema.py` | Reads `table_schema_catalog` (asyncpg) |
| `app/agent/sql_executor.py` | API wrapper for execution |
| `app/db/query_runner.py` | Validates SQL, connects to customer DB or DuckDB, returns rows |
| `app/db/sql_validation.py` | Read-only SQL checks |
| `app/db/learnings.py` | `query_attempts` and `confirmed_learnings` |
| `app/storage/xlsx_ingest.py` | Excel → DuckDB ingest |

## Notes

- Frontend lives in the sibling `frontend/` app (Vite on port 8080).
- App DB pool and external connectors never share a pool or connection.
- All Lens app-DB and customer Postgres I/O uses **asyncpg** (no SQLAlchemy).
- Excel query execution uses **DuckDB**, not asyncpg.
- `db_password` is stored in plaintext for now — intentional tradeoff with a TODO to encrypt before production.
