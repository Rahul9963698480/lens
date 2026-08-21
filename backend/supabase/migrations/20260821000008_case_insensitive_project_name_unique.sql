-- Enforce unique project names case-insensitively (trimmed)
ALTER TABLE projects DROP CONSTRAINT IF EXISTS projects_name_unique;
DROP INDEX IF EXISTS projects_name_unique_ci;
CREATE UNIQUE INDEX projects_name_unique_ci ON projects (LOWER(TRIM(name)));
