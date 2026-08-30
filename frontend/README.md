# XYMP Lens frontend

Vite + React + TypeScript UI for Lens: project list, workspace schema, and Playground analysis chat.

## Setup

```bash
cd frontend
npm install
npm run dev
```

Dev server: **http://localhost:8080**

API calls go through the Vite proxy (`vite.config.ts`) to **http://127.0.0.1:8000** (`/projects`, `/health`). Start the backend first (`uvicorn` from `backend/`). Dev proxy timeout is 5 minutes so long analysis runs do not drop.

Optional: set `VITE_API_URL` if you are not using the proxy.

## App routes

| Path | Screen |
|------|--------|
| `/` | Projects (create Postgres / Excel) |
| `/table/:projectId` | Workspace (schema) and **Playground** |

## Playground

Left **Chats** list (`conversation-sidebar.tsx`): new chat, open a thread, delete (hover trash).

Ask a question → confirm SQL → run. Tabs on the assistant message: **Analysis** (prose bullets), **Data** (table), **Query** (SQL), **Graph**.

Thumbs up/down on a query opens **learnings** (rule text + confirmed SQL) so later questions can reuse the pattern.

Workspace tab: table explorer, schema, preview (DuckDB for Excel projects).

### Chat history

- Each finished turn is stored as question + SQL + analysis answer (`playground_messages`).
- `queries_used` is kept so Data / Query / Graph can restore. It is **not** sent to the LLM on the next question.
- Follow-ups (for example “which region is **he** from”) use the last N turns of Q + SQL + answer from the backend.

APIs used:

- `POST /projects/{id}/analysis/start` (optional `conversation_id`)
- `POST /projects/{id}/analysis/{analysisId}/run?stream=1&conversation_id=...`
- `GET /projects/{id}/conversations`
- `GET /projects/{id}/conversations/{conversationId}`
- `DELETE /projects/{id}/conversations/{conversationId}`
- `PATCH /projects/{id}/attempts/{attemptId}/feedback`
- `POST /projects/{id}/attempts/{attemptId}/confirm`

Other UI APIs: `GET/POST /projects`, `POST /projects/upload-xlsx`, `GET .../schema`, `GET .../preview`, schema annotation PATCHes.

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Vite on port 8080 |
| `npm run build` | Production build |
| `npm run lint` | ESLint |
| `npm run preview` | Preview production build |
