import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

type AnalysisConfirmDialogProps = {
  open: boolean
  proposedSql: string
  message: string
  confirming?: boolean
  onConfirm: () => void
  onClose: () => void
}

export function AnalysisConfirmDialog({
  open,
  proposedSql,
  message,
  confirming,
  onConfirm,
  onClose,
}: AnalysisConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen) onClose()
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Grant permission</DialogTitle>
          <DialogDescription>{message}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={confirming}>
              Cancel
            </Button>
          </DialogClose>
          <Button
            type="button"
            disabled={confirming}
            className="bg-brand-teal text-white hover:bg-brand-teal/90"
            onClick={onConfirm}
          >
            {confirming ? 'Running…' : 'Confirm'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
