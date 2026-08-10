import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { SchemaRelationship } from '@/types/project'

type RelationshipsTabProps = {
  relationships: SchemaRelationship[]
  tableName: string
}

export function RelationshipsTab({ relationships, tableName }: RelationshipsTabProps) {
  if (relationships.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No relationships found for {tableName}.
      </p>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="px-4">From</TableHead>
            <TableHead className="px-4">To</TableHead>
            <TableHead className="px-4">Cardinality</TableHead>
            <TableHead className="px-4">Confidence</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {relationships.map((rel, index) => (
            <TableRow key={`${rel.from_table}-${rel.from_column}-${index}`}>
              <TableCell className="px-4 font-mono text-sm">
                {rel.from_table}.{rel.from_column}
              </TableCell>
              <TableCell className="px-4 font-mono text-sm">
                {rel.to_table}.{rel.to_column}
              </TableCell>
              <TableCell className="px-4">{rel.cardinality.replace(/_/g, ' ')}</TableCell>
              <TableCell className="px-4 capitalize">{rel.confidence}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
