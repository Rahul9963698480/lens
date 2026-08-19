CREATE TABLE IF NOT EXISTS query_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    generated_sql TEXT NOT NULL,
    executed_sql TEXT,
    execution_status TEXT,
    result_row_count INT,
    feedback TEXT NOT NULL DEFAULT 'unknown',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS confirmed_learnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    confirmed_sql TEXT NOT NULL,
    rule_text TEXT,
    source_attempt_id UUID REFERENCES query_attempts(id),
    search_text TEXT GENERATED ALWAYS AS (
        COALESCE(question, '') || ' ' || COALESCE(rule_text, '')
    ) STORED,
    confirmed_at TIMESTAMPTZ DEFAULT now(),
    active BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX ON confirmed_learnings USING GIN (to_tsvector('english', search_text));
