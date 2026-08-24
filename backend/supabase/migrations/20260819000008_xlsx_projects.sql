ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS file_path TEXT;

ALTER TABLE projects ALTER COLUMN db_host DROP NOT NULL;
ALTER TABLE projects ALTER COLUMN db_port DROP NOT NULL;
ALTER TABLE projects ALTER COLUMN db_username DROP NOT NULL;
ALTER TABLE projects ALTER COLUMN db_password DROP NOT NULL;

ALTER TABLE projects DROP CONSTRAINT IF EXISTS projects_engine_check;
ALTER TABLE projects ADD CONSTRAINT projects_engine_check
  CHECK (engine IN ('postgres', 'mongodb', 'xlsx'));

INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('xlsx-projects', 'xlsx-projects', false, 52428800)
ON CONFLICT (id) DO NOTHING;
