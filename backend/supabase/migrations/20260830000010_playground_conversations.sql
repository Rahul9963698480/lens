CREATE TABLE IF NOT EXISTS playground_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS playground_conversations_project_updated_idx
    ON playground_conversations (project_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS playground_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES playground_conversations(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    sql TEXT NOT NULL,
    answer TEXT NOT NULL,
    analysis_id UUID,
    queries_used JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS playground_messages_conversation_created_idx
    ON playground_messages (conversation_id, created_at ASC);
