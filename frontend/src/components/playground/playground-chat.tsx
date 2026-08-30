import { ArrowRight, Mic, Plus, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { AnalysisConfirmDialog } from '@/components/playground/analysis-confirm-dialog'
import { AnalysisResultCard } from '@/components/playground/analysis-result-card'
import { ConversationSidebar } from '@/components/playground/conversation-sidebar'
import { FeedbackRuleDialog } from '@/components/playground/feedback-rule-dialog'
import {
  Attachment,
  AttachmentAction,
  AttachmentActions,
  AttachmentContent,
  AttachmentMedia,
  AttachmentTitle,
} from '@/components/ui/attachment'
import { BrandSpinner } from '@/components/ui/brand-loader'
import { Bubble, BubbleContent } from '@/components/ui/bubble'
import { Button } from '@/components/ui/button'
import { Message, MessageContent, MessageGroup } from '@/components/ui/message'
import { useQueryClient } from '@tanstack/react-query'
import { useRunAnalysis, useStartAnalysis, useSubmitFeedback, useConversations, useDeleteConversation, projectKeys } from '@/hooks/use-projects'
import { apiErrorMessage, projectsApi } from '@/lib/api'
import { notify } from '@/lib/notify'
import { cn } from '@/lib/utils'
import type { AnalysisRunResponse } from '@/types/analysis'
import type { PlaygroundMessage } from '@/types/conversation'

const MAX_FILES = 10

type ChatAttachment = {
  id: string
  file: File
  url: string
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  attachments: ChatAttachment[]
  generating?: boolean
  running?: boolean
  runningStage?: string
  analysisResult?: AnalysisRunResponse
  error?: string
}

type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}

function createId() {
  return crypto.randomUUID()
}

function getSpeechRecognition(): SpeechRecognitionLike | null {
  const speechWindow = window as Window & {
    SpeechRecognition?: new () => SpeechRecognitionLike
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
  }
  const Ctor = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition
  return Ctor ? new Ctor() : null
}

function errorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  const axiosData =
    typeof error === 'object' && error !== null && 'response' in error
      ? (error as { response?: { data?: unknown } }).response?.data
      : undefined
  return apiErrorMessage(axiosData, fallback)
}

function ChatComposer({
  draft,
  files,
  listening,
  compact,
  onDraftChange,
  onAttachClick,
  onRemoveFile,
  onToggleMic,
  onSubmit,
}: {
  draft: string
  files: ChatAttachment[]
  listening: boolean
  compact?: boolean
  onDraftChange: (value: string) => void
  onAttachClick: () => void
  onRemoveFile: (id: string) => void
  onToggleMic: () => void
  onSubmit: () => void
}) {
  const canSend = draft.trim().length > 0 || files.length > 0

  return (
    <div className="mx-auto w-full max-w-2xl">
      {files.length > 0 ? (
        <div className="mb-3 flex flex-wrap gap-2 px-1">
          {files.map((item) => (
            <Attachment key={item.id} size="sm" className="pr-1">
              <AttachmentMedia variant="image">
                <img src={item.url} alt={item.file.name} />
              </AttachmentMedia>
              <AttachmentContent>
                <AttachmentTitle>{item.file.name}</AttachmentTitle>
              </AttachmentContent>
              <AttachmentActions>
                <AttachmentAction
                  aria-label={`Remove ${item.file.name}`}
                  onClick={() => onRemoveFile(item.id)}
                >
                  <X />
                </AttachmentAction>
              </AttachmentActions>
            </Attachment>
          ))}
        </div>
      ) : null}

      <form
        className={cn(
          'flex items-center gap-1 rounded-full border border-border/80 bg-background pr-1.5 pl-1.5 shadow-[0_4px_18px_rgba(15,23,42,0.08)]',
          compact ? 'h-12' : 'h-14',
        )}
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit()
        }}
      >
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Attach files"
          className="size-9 shrink-0 rounded-full text-muted-foreground hover:text-foreground"
          onClick={onAttachClick}
        >
          <Plus className="size-5" strokeWidth={2} />
        </Button>

        <input
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          placeholder="Ask a question or attach files to get started"
          className="h-full min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/80"
        />

        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={listening ? 'Stop voice input' : 'Start voice input'}
          aria-pressed={listening}
          className={cn(
            'size-9 shrink-0 rounded-full text-muted-foreground hover:text-foreground',
            listening && 'bg-brand-teal/10 text-brand-teal',
          )}
          onClick={onToggleMic}
        >
          <Mic className="size-5" strokeWidth={1.75} />
        </Button>

        <Button
          type="submit"
          size="icon"
          aria-label="Send message"
          disabled={!canSend}
          className="size-9 shrink-0 rounded-full bg-brand-teal text-white hover:bg-brand-teal/90 disabled:opacity-100"
        >
          <ArrowRight className="size-4" strokeWidth={2.5} />
        </Button>
      </form>

      {/* <p className="mt-3 text-center text-xs text-muted-foreground">
        Supports Images · Max {MAX_FILES} files · use + to attach
      </p> */}
    </div>
  )
}

function turnsToMessages(turns: PlaygroundMessage[]): ChatMessage[] {
  return turns.flatMap((turn) => [
    {
      id: `${turn.id}-q`,
      role: 'user' as const,
      content: turn.question,
      attachments: [],
    },
    {
      id: `${turn.id}-a`,
      role: 'assistant' as const,
      content: '',
      attachments: [],
      analysisResult: {
        analysis_id: turn.analysis_id ?? turn.id,
        answer: turn.answer,
        queries_used:
          turn.queries_used && turn.queries_used.length > 0
            ? turn.queries_used
            : [
                {
                  attempt_id: turn.id,
                  sql: turn.sql,
                  result_summary: {
                    status: 'ok',
                    columns: [],
                    row_count: 0,
                    rows_preview: [],
                  },
                },
              ],
      },
    },
  ])
}

export function PlaygroundChat({ projectId }: { projectId?: string }) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const objectUrlsRef = useRef<string[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [draft, setDraft] = useState('')
  const [files, setFiles] = useState<ChatAttachment[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [listening, setListening] = useState(false)
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean
    messageId: string
    analysisId: string
    proposedSql: string
    message: string
  } | null>(null)
  const [feedbackDialog, setFeedbackDialog] = useState<{
    open: boolean
    sql: string
    attemptId: string
    feedback: 'correct' | 'incorrect'
  } | null>(null)
  const startAnalysis = useStartAnalysis()
  const runAnalysis = useRunAnalysis()
  const submitFeedback = useSubmitFeedback()
  const queryClient = useQueryClient()
  const conversationsQuery = useConversations(projectId)
  const deleteConversation = useDeleteConversation(projectId)
  const [conversationId, setConversationId] = useState<string | null>(null)

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop()
      objectUrlsRef.current.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const updateMessage = (id: string, patch: Partial<ChatMessage>) => {
    setMessages((current) =>
      current.map((message) => (message.id === id ? { ...message, ...patch } : message)),
    )
  }

  const handleAttachClick = () => {
    fileInputRef.current?.click()
  }

  const handleFilesSelected = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (selected.length === 0) {
      return
    }

    const remaining = MAX_FILES - files.length
    if (remaining <= 0) {
      notify.error(`You can attach up to ${MAX_FILES} files.`)
      return
    }

    const nextFiles = selected.slice(0, remaining).map((file) => {
      const url = URL.createObjectURL(file)
      objectUrlsRef.current.push(url)
      return {
        id: createId(),
        file,
        url,
      }
    })

    if (selected.length > remaining) {
      notify.error(`Only ${MAX_FILES} files can be attached. Extra files were skipped.`)
    }

    setFiles((current) => [...current, ...nextFiles])
  }

  const handleRemoveFile = (id: string) => {
    setFiles((current) => {
      const removed = current.find((item) => item.id === id)
      if (removed) {
        URL.revokeObjectURL(removed.url)
      }
      return current.filter((item) => item.id !== id)
    })
  }

  const handleToggleMic = () => {
    if (listening) {
      recognitionRef.current?.stop()
      setListening(false)
      return
    }

    const recognition = getSpeechRecognition()
    if (!recognition) {
      notify.error('Voice input is not supported in this browser.')
      return
    }

    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = 'en-US'
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? '')
        .join(' ')
        .trim()
      if (transcript) {
        setDraft((current) => (current ? `${current} ${transcript}` : transcript))
      }
    }
    recognition.onerror = () => setListening(false)
    recognition.onend = () => setListening(false)
    recognitionRef.current = recognition
    recognition.start()
    setListening(true)
  }

  const handleSubmit = async () => {
    const content = draft.trim()
    if (!content && files.length === 0) {
      return
    }

    if (!projectId) {
      notify.error('Project is missing.')
      return
    }

    const userMessage: ChatMessage = {
      id: createId(),
      role: 'user',
      content,
      attachments: files,
    }
    const assistantMessage: ChatMessage = {
      id: createId(),
      role: 'assistant',
      content: content
        ? ''
        : 'Ask a question about this project\'s data to generate SQL.',
      attachments: [],
      generating: Boolean(content),
    }

    setMessages((current) => [...current, userMessage, assistantMessage])
    setDraft('')
    setFiles([])

    if (!content) {
      return
    }

    try {
      const response = await startAnalysis.mutateAsync({
        projectId,
        question: content,
        conversationId,
      })
      setConversationId(response.conversation_id)
      void queryClient.invalidateQueries({
        queryKey: projectKeys.conversations(projectId),
      })
      updateMessage(assistantMessage.id, {
        generating: false,
        error: undefined,
      })
      setConfirmDialog({
        open: true,
        messageId: assistantMessage.id,
        analysisId: response.analysis_id,
        proposedSql: response.proposed_sql,
        message: response.message,
      })
    } catch (error) {
      updateMessage(assistantMessage.id, {
        generating: false,
        error: errorMessage(error, 'Failed to start analysis.'),
      })
    }
  }

  const handleConfirmAnalysis = async () => {
    if (!projectId || !confirmDialog) {
      return
    }

    const { messageId, analysisId } = confirmDialog

    updateMessage(messageId, {
      running: true,
      runningStage: 'Running query…',
      error: undefined,
      analysisResult: undefined,
    })

    try {
      const result = await runAnalysis.mutateAsync({
        projectId,
        analysisId,
        conversationId,
        onProgress: (_stage, message) => {
          updateMessage(messageId, {
            running: true,
            runningStage: message || 'Running analysis…',
          })
        },
      })
      updateMessage(messageId, {
        running: false,
        runningStage: undefined,
        analysisResult: result,
      })
      setConfirmDialog(null)
      if (projectId) {
        void queryClient.invalidateQueries({
          queryKey: projectKeys.conversations(projectId),
        })
      }
    } catch (error) {
      updateMessage(messageId, {
        running: false,
        error: errorMessage(error, 'Failed to run analysis.'),
      })
      setConfirmDialog(null)
    }
  }

  const handleCancelAnalysis = () => {
    if (confirmDialog) {
      updateMessage(confirmDialog.messageId, {
        content: 'Analysis cancelled.',
      })
    }
    setConfirmDialog(null)
  }

  const handleSqlChange = (messageId: string, attemptId: string, sql: string) => {
    setMessages((current) =>
      current.map((message) => {
        if (message.id !== messageId || !message.analysisResult) {
          return message
        }

        return {
          ...message,
          analysisResult: {
            ...message.analysisResult,
            queries_used: message.analysisResult.queries_used.map((query) =>
              query.attempt_id === attemptId ? { ...query, sql } : query,
            ),
          },
        }
      }),
    )
  }

  const handleFeedback = async (
    messageId: string,
    attemptId: string,
    feedback: 'correct' | 'incorrect',
  ) => {
    if (!projectId) {
      notify.error('Project is missing.')
      return
    }

    const message = messages.find((m) => m.id === messageId)
    const sql =
      message?.analysisResult?.queries_used.find((query) => query.attempt_id === attemptId)
        ?.sql ?? ''

    try {
      await submitFeedback.mutateAsync({
        projectId,
        attemptId,
        feedback,
      })
      setFeedbackDialog({
        open: true,
        sql,
        attemptId,
        feedback,
      })
    } catch (error) {
      notify.error(errorMessage(error, 'Failed to submit feedback.'))
    }
  }

  const handleNewChat = () => {
    setConversationId(null)
    setMessages([])
    setConfirmDialog(null)
  }

  const handleDeleteConversation = async (id: string) => {
    if (!projectId) {
      return
    }
    if (!window.confirm('Delete this chat? This cannot be undone.')) {
      return
    }
    try {
      await deleteConversation.mutateAsync({
        projectId,
        conversationId: id,
      })
      if (conversationId === id) {
        handleNewChat()
      }
    } catch (error) {
      notify.error(errorMessage(error, 'Failed to delete chat.'))
    }
  }

  const handleSelectConversation = async (id: string) => {
    if (!projectId) {
      return
    }
    try {
      const detail = await projectsApi.getConversation(projectId, id)
      setConversationId(id)
      setMessages(turnsToMessages(detail.messages))
    } catch (error) {
      notify.error(errorMessage(error, 'Failed to load chat.'))
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="flex min-h-0 flex-1 bg-background">
      <ConversationSidebar
        conversations={conversationsQuery.data ?? []}
        selectedId={conversationId}
        onSelect={(id) => {
          void handleSelectConversation(id)
        }}
        onNewChat={handleNewChat}
        onDelete={(id) => {
          void handleDeleteConversation(id)
        }}
        deletingId={
          deleteConversation.isPending
            ? deleteConversation.variables?.conversationId
            : null
        }
      />
      <div className="flex min-h-0 flex-1 flex-col">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={handleFilesSelected}
      />

      {isEmpty ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-8 px-4 pb-16">
          <p className="text-center text-2xl font-medium tracking-tight text-foreground sm:text-[1.65rem]">
            Hi! How can I help today?
          </p>
          <ChatComposer
            draft={draft}
            files={files}
            listening={listening}
            onDraftChange={setDraft}
            onAttachClick={handleAttachClick}
            onRemoveFile={handleRemoveFile}
            onToggleMic={handleToggleMic}
            onSubmit={handleSubmit}
          />
        </div>
      ) : (
        <>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6">
            <MessageGroup className="mx-auto w-full max-w-2xl gap-4">
              {messages.map((message) => (
                <Message
                  key={message.id}
                  align={message.role === 'user' ? 'end' : 'start'}
                >
                  <MessageContent>
                    {message.attachments.length > 0 ? (
                      <div className="mb-2 flex flex-wrap justify-end gap-2">
                        {message.attachments.map((item) => (
                          <img
                            key={item.id}
                            src={item.url}
                            alt={item.file.name}
                            className="h-20 w-20 rounded-lg object-cover"
                          />
                        ))}
                      </div>
                    ) : null}
                    {message.content ? (
                      <Bubble variant="muted">
                        <BubbleContent
                          className={
                            message.role === 'user'
                              ? 'rounded-2xl bg-muted px-4 py-2.5 text-foreground'
                              : undefined
                          }
                        >
                          {message.content}
                        </BubbleContent>
                      </Bubble>
                    ) : null}
                    {message.generating ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <BrandSpinner size={18} label="Starting analysis" />
                        Starting analysis…
                      </div>
                    ) : null}
                    {message.running ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <BrandSpinner size={18} label="Running analysis" />
                        {message.runningStage || 'Running analysis…'}
                      </div>
                    ) : null}
                    {message.error && !message.analysisResult ? (
                      <Bubble variant="destructive">
                        <BubbleContent>{message.error}</BubbleContent>
                      </Bubble>
                    ) : null}
                    {message.analysisResult ? (
                      <AnalysisResultCard
                        result={message.analysisResult}
                        onSqlChange={(attemptId, sql) =>
                          handleSqlChange(message.id, attemptId, sql)
                        }
                        onFeedback={(attemptId, feedback) =>
                          handleFeedback(message.id, attemptId, feedback)
                        }
                      />
                    ) : null}
                  </MessageContent>
                </Message>
              ))}
              <div ref={messagesEndRef} />
            </MessageGroup>
          </div>
          <div className="px-4 pb-6 pt-2">
            <ChatComposer
              compact
              draft={draft}
              files={files}
              listening={listening}
              onDraftChange={setDraft}
              onAttachClick={handleAttachClick}
              onRemoveFile={handleRemoveFile}
              onToggleMic={handleToggleMic}
              onSubmit={handleSubmit}
            />
          </div>
        </>
      )}

      {confirmDialog ? (
        <AnalysisConfirmDialog
          open={confirmDialog.open}
          proposedSql={confirmDialog.proposedSql}
          message={confirmDialog.message}
          confirming={runAnalysis.isPending}
          onConfirm={handleConfirmAnalysis}
          onClose={handleCancelAnalysis}
        />
      ) : null}

      {feedbackDialog && projectId ? (
        <FeedbackRuleDialog
          open={feedbackDialog.open}
          sql={feedbackDialog.sql}
          feedback={feedbackDialog.feedback}
          projectId={projectId}
          attemptId={feedbackDialog.attemptId}
          onClose={() => setFeedbackDialog(null)}
        />
      ) : null}
      </div>
    </div>
  )
}
