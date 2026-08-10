import type { ColumnAnnotationPayload, SchemaColumn } from '@/types/project'



export type ColumnAnnotation = {

  description: string

  businessName: string

  nullMeaning: string

  valueMapping: string

  caveats: string

}



export const EMPTY_COLUMN_ANNOTATION: ColumnAnnotation = {

  description: '',

  businessName: '',

  nullMeaning: '',

  valueMapping: '',

  caveats: '',

}



export function formatValueMappings(

  mappings: Record<string, unknown> | null | undefined,

): string {

  if (!mappings) return ''

  return Object.entries(mappings)

    .map(([key, value]) => `${key} = ${String(value)}`)

    .join('\n')

}



export function parseValueMappings(text: string): Record<string, string> | null {

  const trimmed = text.trim()

  if (!trimmed) return null



  const result: Record<string, string> = {}

  for (const line of trimmed.split('\n')) {

    const match = line.match(/^(.+?)\s*=\s*(.+)$/)

    if (match) {

      result[match[1].trim()] = match[2].trim()

    }

  }



  return Object.keys(result).length > 0 ? result : null

}



export function columnAnnotationFromSchema(column: SchemaColumn): ColumnAnnotation {

  return {

    description: column.description ?? '',

    businessName: column.business_name ?? '',

    nullMeaning: column.null_meanings ?? '',

    valueMapping: formatValueMappings(column.value_mappings),

    caveats: column.caveats ?? '',

  }

}



export function columnAnnotationToPayload(

  annotation: ColumnAnnotation,

): ColumnAnnotationPayload {

  return {

    description: annotation.description || null,

    business_name: annotation.businessName || null,

    null_meanings: annotation.nullMeaning || null,

    value_mappings: parseValueMappings(annotation.valueMapping),

    caveats: annotation.caveats || null,

  }

}



export const COLUMN_ANNOTATION_FIELDS: {
  key: keyof ColumnAnnotation
  label: string
}[] = [
    { key: 'description', label: 'Description' },
    { key: 'businessName', label: 'Business name' },
    { key: 'nullMeaning', label: 'Null meaning' },
    { key: 'valueMapping', label: 'Value mapping' },
    { key: 'caveats', label: 'Caveats' },
  ]

export function hasColumnAnnotation(column: SchemaColumn): boolean {
  const annotation = columnAnnotationFromSchema(column)
  return COLUMN_ANNOTATION_FIELDS.some(({ key }) => Boolean(annotation[key]))
}

export function tableAnnotationFromSchema(table: {
  table_description?: string | null
  business_name?: string | null
}): ColumnAnnotation {
  return {
    description: table.table_description ?? '',
    businessName: table.business_name ?? '',
    nullMeaning: '',
    valueMapping: '',
    caveats: '',
  }
}

export function hasTableAnnotation(table: {
  table_description?: string | null
  business_name?: string | null
}): boolean {
  const annotation = tableAnnotationFromSchema(table)
  return Boolean(annotation.description || annotation.businessName)
}


