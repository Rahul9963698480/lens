import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'

const annotateButtonClassName =
  'border-brand-teal/30 bg-brand-teal/10 text-brand-teal hover:border-brand-teal/45 hover:bg-brand-teal/20 hover:text-brand-teal'

type AnnotateButtonProps = {
  onClick: () => void
  children: ReactNode
}

export function AnnotateButton({ onClick, children }: AnnotateButtonProps) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className={annotateButtonClassName}
      onClick={onClick}
    >
      {children}
    </Button>
  )
}
