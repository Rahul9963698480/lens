import { ChevronDown, ChevronRight, Folder, Table2 } from 'lucide-react'
import { useState } from 'react'

import { cn } from '@/lib/utils'

type TableExplorerProps = {
  tables: string[]
  selectedTable: string | null
  onSelectTable: (tableName: string) => void
}

export function TableExplorer({
  tables,
  selectedTable,
  onSelectTable,
}: TableExplorerProps) {
  const [publicExpanded, setPublicExpanded] = useState(true)
  const [tablesExpanded, setTablesExpanded] = useState(true)

  return (
    <aside className="flex min-h-0 w-56 shrink-0 flex-col border-r bg-background">
      <div className="border-b px-3 py-2.5">
        <span className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
          Explorer
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto p-2">
        <div className="mb-1">
          <button
            type="button"
            onClick={() => setPublicExpanded((value) => !value)}
            className="flex w-full items-center gap-1 rounded-md px-2 py-1 text-sm font-medium text-foreground hover:bg-muted/60"
          >
            {publicExpanded ? (
              <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
            )}
            <Folder className="size-3.5 shrink-0 text-muted-foreground" />
            <span>public</span>
          </button>

          {publicExpanded && (
            <div className="mt-0.5 ml-2 border-l border-border pl-2">
              <button
                type="button"
                onClick={() => setTablesExpanded((value) => !value)}
                className="flex w-full items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted/60 hover:text-foreground"
              >
                {tablesExpanded ? (
                  <ChevronDown className="size-3 shrink-0" />
                ) : (
                  <ChevronRight className="size-3 shrink-0" />
                )}
                <Table2 className="size-3 shrink-0" />
                <span>Tables</span>
                <span className="ml-auto text-[11px] tabular-nums text-muted-foreground/70">
                  {tables.length}
                </span>
              </button>

              {tablesExpanded && (
                <ul className="mt-0.5 space-y-0.5">
                  {tables.map((tableName) => (
                    <li key={tableName}>
                      <button
                        type="button"
                        onClick={() => onSelectTable(tableName)}
                        className={cn(
                          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors',
                          selectedTable === tableName
                            ? 'bg-muted font-medium text-foreground'
                            : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
                        )}
                      >
                        <Table2 className="size-3.5 shrink-0" />
                        <span className="truncate">{tableName}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </nav>
    </aside>
  )
}
