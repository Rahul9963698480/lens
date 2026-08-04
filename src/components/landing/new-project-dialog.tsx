import { useCallback, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { cn } from '@/lib/utils'

const DATABASE_OPTIONS = [
  { value: 'sqlite', label: 'SQLite' },
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'mysql', label: 'MySQL' },
  { value: 'mongodb', label: 'MongoDB' },
] as const

type DatabaseType = (typeof DATABASE_OPTIONS)[number]['value']

type NewProjectDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function NewProjectDialog({ open, onOpenChange }: NewProjectDialogProps) {
  const [projectName, setProjectName] = useState('')
  const [database, setDatabase] = useState<DatabaseType>('sqlite')
  const [host, setHost] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const isFormValid =
    projectName.trim() !== '' &&
    host.trim() !== '' &&
    username.trim() !== '' &&
    password.trim() !== ''

  const handleDatabaseChange = useCallback((value: DatabaseType) => {
    setDatabase(value)
    setHost('')
    setUsername('')
    setPassword('')
  }, [])

  const handleCreate = useCallback(() => {
    if (!isFormValid) return
    // Project creation will be wired to the API soon.
    onOpenChange(false)
  }, [isFormValid, onOpenChange])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-5 sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New project</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="project-name">
              Project name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="project-name"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="Sales Database"
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label>Database</Label>
            <RadioGroup
              value={database}
              onValueChange={handleDatabaseChange}
              className="grid grid-cols-2 gap-2"
            >
              {DATABASE_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  htmlFor={`database-${option.value}`}
                  className={cn(
                    'flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 transition-colors',
                    database === option.value
                      ? 'border-foreground/30 bg-muted/40'
                      : 'border-border hover:border-foreground/20',
                  )}
                >
                  <RadioGroupItem
                    id={`database-${option.value}`}
                    value={option.value}
                  />
                  <span className="text-sm font-medium">{option.label}</span>
                </label>
              ))}
            </RadioGroup>
          </div>

          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="connection-host">
                Host <span className="text-destructive">*</span>
              </Label>
              <Input
                id="connection-host"
                value={host}
                onChange={(event) => setHost(event.target.value)}
                placeholder={database === 'sqlite' ? 'data/sales.db' : 'localhost'}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="connection-username">
                Username <span className="text-destructive">*</span>
              </Label>
              <Input
                id="connection-username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="user"
                autoComplete="username"
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="connection-password">
                Password <span className="text-destructive">*</span>
              </Label>
              <Input
                id="connection-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="password"
                autoComplete="current-password"
                required
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <Button
            type="button"
            className="bg-brand-navy text-white hover:bg-brand-navy/90 disabled:opacity-50"
            onClick={handleCreate}
            disabled={!isFormValid}
          >
            Create
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
