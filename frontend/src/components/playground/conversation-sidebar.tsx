import { MessageSquarePlus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { PlaygroundConversation } from '@/types/conversation'

type ConversationSidebarProps = {
  conversations: PlaygroundConversation[]
  selectedId: string | null
  onSelect: (conversationId: string) => void
  onNewChat: () => void
  onDelete: (conversationId: string) => void
  deletingId?: string | null
}

export function ConversationSidebar({
  conversations,
  selectedId,
  onSelect,
  onNewChat,
  onDelete,
  deletingId,
}: ConversationSidebarProps) {
  return (
    <aside className="flex min-h-0 w-56 shrink-0 flex-col border-r bg-background">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2.5">
        <span className="text-[10px] font-semibold tracking-wider text-foreground/80 uppercase">
          Chats
        </span>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 gap-1 px-2 text-xs"
          onClick={onNewChat}
        >
          <MessageSquarePlus className="size-3.5" />
          New
        </Button>
      </div>
      <nav className="flex-1 overflow-y-auto p-2">
        {conversations.length === 0 ? (
          <p className="px-2 py-3 text-xs text-muted-foreground">
            No chats yet. Ask a question to start.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((item) => (
              <li key={item.id}>
                <div
                  className={cn(
                    'group flex w-full items-center rounded-md transition-colors',
                    selectedId === item.id
                      ? 'bg-primary/10'
                      : 'hover:bg-muted/60',
                  )}
                >
                  <button
                    type="button"
                    onClick={() => onSelect(item.id)}
                    className={cn(
                      'min-w-0 flex-1 px-2 py-1.5 text-left text-sm',
                      selectedId === item.id
                        ? 'font-medium text-primary'
                        : 'text-foreground/85 group-hover:text-foreground',
                    )}
                  >
                    <span className="block truncate">{item.title}</span>
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${item.title}`}
                    disabled={deletingId === item.id}
                    onClick={(event) => {
                      event.stopPropagation()
                      onDelete(item.id)
                    }}
                    className="mr-1 shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100 focus-visible:opacity-100 disabled:opacity-50"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </nav>
    </aside>
  )
}
