export type ProjectEngine = 'postgres' | 'mongodb'

export type CreateProjectPayload = {
  name: string
  engine: ProjectEngine
  db_host: string
  db_name: string
  db_username: string
  db_password: string
}

export type Project = {
  id: string
  name: string
  engine: string
  db_host: string
  db_port: number
  db_name: string
  db_username: string
  status: string
  created_at: string
}

export type SchemaColumn = {
  name: string
  type?: string | null
  inferred_type?: string | null
  nullable?: boolean | null
  primary_key?: boolean | null
  foreign_key?: string | null
  presence_pct?: number | null
  description?: string | null
  business_name?: string | null
  value_mappings?: Record<string, unknown> | null
  null_meanings?: string | null
  caveats?: string | null
}

export type SchemaRelationship = {
  from_table: string
  from_column: string
  to_table: string
  to_column: string
  cardinality: string
  confidence: string
}

export type TableSchema = {
  table_name: string
  table_description?: string | null
  business_name?: string | null
  columns: SchemaColumn[]
  relationships: SchemaRelationship[]
  inferred: boolean
  updated_at?: string
}

export type ProjectSchemaResponse = {
  project_id: string
  db_name: string
  tables: TableSchema[]
}

export type TablePreview = {
  table_name: string
  columns: string[]
  rows?: Record<string, unknown>[]
  error?: string
}

export type ProjectPreviewResponse = {
  project_id: string
  tables: TablePreview[]
}

export type TableAnnotationPayload = {
  table_description?: string | null
  business_name?: string | null
}

export type ColumnAnnotationPayload = {
  description?: string | null
  business_name?: string | null
  value_mappings?: Record<string, unknown> | null
  null_meanings?: string | null
  caveats?: string | null
}
