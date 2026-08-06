CREATE TABLE IF NOT EXISTS table_schema_catalog (
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    db_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    columns JSONB NOT NULL DEFAULT '[]'::jsonb,
    relationships JSONB NOT NULL DEFAULT '[]'::jsonb,
    inferred BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, table_name)
);
