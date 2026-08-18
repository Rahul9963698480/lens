-- Add a UNIQUE constraint on project name to prevent duplicates
ALTER TABLE projects ADD CONSTRAINT projects_name_unique UNIQUE (name);
