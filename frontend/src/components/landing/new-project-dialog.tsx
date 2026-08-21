import { useCallback, useEffect, useRef, useState } from 'react'

import { DiscoveringDatabaseDialog } from '@/components/landing/discovering-database-dialog'
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
import { useCreateProject } from '@/hooks/use-projects'
import { cn } from '@/lib/utils'
import type { ProjectEngine } from '@/types/project'

const DISCOVERY_CLOSE_DELAY_MS = 500

const DATABASE_OPTIONS = [
  { value: 'postgres', label: 'PostgreSQL' },
  { value: 'mongodb', label: 'MongoDB' },
] as const satisfies ReadonlyArray<{ value: ProjectEngine; label: string }>

type NewProjectDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const INITIAL_FORM = {
  projectName: '',
  engine: 'postgres' as ProjectEngine,
  host: '',
  dbName: '',
  username: '',
  password: '',
}

export function NewProjectDialog({ open, onOpenChange }: NewProjectDialogProps) {
  const [projectName, setProjectName] = useState(INITIAL_FORM.projectName)
  const [engine, setEngine] = useState<ProjectEngine>(INITIAL_FORM.engine)
  const [host, setHost] = useState(INITIAL_FORM.host)
  const [dbName, setDbName] = useState(INITIAL_FORM.dbName)
  const [username, setUsername] = useState(INITIAL_FORM.username)
  const [password, setPassword] = useState(INITIAL_FORM.password)
  const [isDiscovering, setIsDiscovering] = useState(false)
  const [discoveryComplete, setDiscoveryComplete] = useState(false)
  const closeTimeoutRef = useRef<number | null>(null)

  const resetForm = useCallback(() => {
    setProjectName(INITIAL_FORM.projectName)
    setEngine(INITIAL_FORM.engine)
    setHost(INITIAL_FORM.host)
    setDbName(INITIAL_FORM.dbName)
    setUsername(INITIAL_FORM.username)
    setPassword(INITIAL_FORM.password)
  }, [])

  const finishDiscovery = useCallback(() => {
    setDiscoveryComplete(true)
    closeTimeoutRef.current = window.setTimeout(() => {
      resetForm()
      setIsDiscovering(false)
      setDiscoveryComplete(false)
      onOpenChange(false)
    }, DISCOVERY_CLOSE_DELAY_MS)
  }, [onOpenChange, resetForm])

  const createMutation = useCreateProject({
    onSuccess: () => {
      finishDiscovery()
    },
    onError: () => {
      setIsDiscovering(false)
      setDiscoveryComplete(false)
    },
  })

  useEffect(() => {
    return () => {
      if (closeTimeoutRef.current !== null) {
        window.clearTimeout(closeTimeoutRef.current)
      }
    }
  }, [])

  const isFormValid =
    projectName.trim() !== '' &&
    host.trim() !== '' &&
    dbName.trim() !== '' &&
    username.trim() !== '' &&
    password.trim() !== ''

  const handleDatabaseChange = useCallback((value: ProjectEngine) => {
    setEngine(value)
    setHost('')
    setDbName('')
    setUsername('')
    setPassword('')
  }, [])

  const handleCreate = useCallback(() => {
    if (!isFormValid || createMutation.isPending || isDiscovering) return

    setIsDiscovering(true)
    setDiscoveryComplete(false)
    createMutation.mutate({
      name: projectName.trim(),
      engine,
      db_host: host.trim(),
      db_name: dbName.trim(),
      db_username: username.trim(),
      db_password: password,
    })
  }, [
    createMutation,
    dbName,
    engine,
    host,
    isDiscovering,
    isFormValid,
    password,
    projectName,
    username,
  ])

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen && (createMutation.isPending || isDiscovering)) {
        return
      }
      if (!nextOpen) {
        if (closeTimeoutRef.current !== null) {
          window.clearTimeout(closeTimeoutRef.current)
          closeTimeoutRef.current = null
        }
        resetForm()
        setIsDiscovering(false)
        setDiscoveryComplete(false)
      }
      onOpenChange(nextOpen)
    },
    [createMutation.isPending, isDiscovering, onOpenChange, resetForm],
  )

  const showFormDialog = open && !isDiscovering

  return (
    <>
    <DiscoveringDatabaseDialog
      open={open && isDiscovering}
      isComplete={discoveryComplete}
    />
    <Dialog open={showFormDialog} onOpenChange={handleOpenChange}>
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 overflow-hidden sm:max-w-md">
        <DialogHeader className="shrink-0">
          <DialogTitle>New project</DialogTitle>
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto py-5 px-5">
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
              value={engine}
              onValueChange={handleDatabaseChange}
              className="grid grid-cols-2 gap-2"
            >
              {DATABASE_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  htmlFor={`database-${option.value}`}
                  className={cn(
                    'flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 transition-colors',
                    engine === option.value
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
                placeholder="localhost"
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="connection-db-name">
                Database name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="connection-db-name"
                value={dbName}
                onChange={(event) => setDbName(event.target.value)}
                placeholder={engine === 'mongodb' ? 'mydb' : 'sales'}
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

        <div className="flex shrink-0 justify-end pt-5">
          <Button
            type="button"
            className="rounded-full px-4 disabled:opacity-50"
            onClick={handleCreate}
            disabled={!isFormValid || createMutation.isPending || isDiscovering}
          >
            Create
          </Button>
        </div>
      </DialogContent>
    </Dialog>
    </>
  )
}
