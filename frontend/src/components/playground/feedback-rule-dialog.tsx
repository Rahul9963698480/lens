import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useConfirmFeedback } from '@/hooks/use-projects'

type FeedbackRuleDialogProps = {
  open: boolean
  sql: string
  feedback: 'correct' | 'incorrect'
  projectId: string
  attemptId: string
  onClose: () => void
}

export function FeedbackRuleDialog({
  open,
  sql,
  feedback,
  projectId,
  attemptId,
  onClose,
}: FeedbackRuleDialogProps) {
  const [editedSql, setEditedSql] = useState(sql)
  const [rule, setRule] = useState('')
  const confirmFeedback = useConfirmFeedback()

  const handleConfirm = async () => {
    await confirmFeedback.mutateAsync({
      projectId,
      attemptId,
      confirmed_sql: editedSql,
      rule_text: rule,
    })
    onClose()
    setRule('')
  }

  const handleClose = () => {
    onClose()
    setRule('')
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen) handleClose()
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            Feedback: {feedback === 'correct' ? 'Correct' : 'Incorrect'}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="feedback-sql">Generated SQL Query</Label>
            <Textarea
              id="feedback-sql"
              value={editedSql}
              onChange={(e) => setEditedSql(e.target.value)}
              className="min-h-24 resize-y font-mono text-sm"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="feedback-rule">Rule</Label>
            <Textarea
              id="feedback-rule"
              value={rule}
              onChange={(e) => setRule(e.target.value)}
              placeholder="Add a rule or note for this feedback…"
              className="min-h-24 resize-y text-sm"
            />
          </div>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              Cancel
            </Button>
          </DialogClose>
          <Button
            type="button"
            disabled={confirmFeedback.isPending}
            className="bg-brand-teal text-white hover:bg-brand-teal/90"
            onClick={handleConfirm}
          >
            {confirmFeedback.isPending ? 'Confirming…' : 'Confirm'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
