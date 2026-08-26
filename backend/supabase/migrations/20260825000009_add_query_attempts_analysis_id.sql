ALTER TABLE query_attempts ADD COLUMN IF NOT EXISTS analysis_id UUID;

CREATE INDEX IF NOT EXISTS query_attempts_analysis_id_idx
  ON query_attempts (analysis_id)
  WHERE analysis_id IS NOT NULL;
