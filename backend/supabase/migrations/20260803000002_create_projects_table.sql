CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name TEXT NOT NULL,
    db_host TEXT NOT NULL,
    db_port INTEGER NOT NULL DEFAULT 5432,
    db_name TEXT NOT NULL,
    db_username TEXT NOT NULL,
    -- TODO: encrypt at rest before production
    db_password TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);
