CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_unique_name_lower ON projects (LOWER(name));
