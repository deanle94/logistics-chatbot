import { Sparkles } from 'lucide-react'

import { ChatComposer } from '@/components/chat/ChatComposer'
import { ChatTurn } from '@/components/chat/ChatTurn'
import { AppHeader } from '@/components/layout/AppHeader'
import { AppSidebar, type AppPage } from '@/components/layout/AppSidebar'
import { useChatStream } from '@/hooks/useChatStream'

type ChatPageProps = {
  onNavigate: (page: AppPage) => void
}

/**
 * S2.6 - the chat page of `docs/design/Chat.dc.html`.
 *
 * Composition only. It holds no networking of its own (that is `useChatStream`), no draft
 * text (that is `ChatComposer`, where it is used), and no formula - every figure on this
 * page was computed by `calculator/` and is printed exactly as it arrived.
 *
 * Every hook is above every return (react rule 12), so no conditional path can reorder them.
 */
export default function ChatPage({ onNavigate }: ChatPageProps) {
  const { turns, pending, ask } = useChatStream()

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <AppSidebar current="chat" onNavigate={onNavigate} />

      <div className="flex min-w-0 grow flex-col">
        <AppHeader page="Ask AI" />

        <main className="flex grow flex-col gap-4 p-6" data-testid="chat-page">
          <div className="mx-auto flex w-full max-w-3xl grow flex-col gap-6">
            {turns.length === 0 ? (
              <div
                className="flex grow flex-col items-center justify-center gap-2 text-center"
                data-testid="chat-empty"
              >
                <Sparkles className="size-6 text-muted-foreground" aria-hidden="true" />
                <h2 className="text-lg font-semibold tracking-tight">Ask about your deliveries</h2>
                <p className="max-w-md text-sm text-muted-foreground">
                  Every answer is counted from your own orders. Nothing is estimated or guessed.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-8 pb-20">
                {/*
                  `pb-20` is load-bearing, not spacing taste. The composer below is
                  `sticky bottom-0`, so it floats over whatever precedes it once the
                  transcript is taller than the viewport - and what precedes it is the last
                  row of the expanded data table. Measured before the fix: last row at
                  y 934-970, composer at y 928-972, so the final carrier was unreadable on
                  every answer. This padding lets the transcript scroll clear of it.
                */}
                {turns.map((turn) => (
                  // The turn id is its identity, so a new question never reuses the DOM
                  // node of an earlier answer (react rule 5).
                  <ChatTurn key={turn.id} turn={turn} onAnswerFollowUp={ask} />
                ))}
              </div>
            )}

            <div className="sticky bottom-0 flex flex-col gap-2 bg-background pt-2 pb-1">
              <ChatComposer disabled={pending} onSubmit={ask} />
              <p className="text-center text-xs text-muted-foreground">
                Answers are counted from your orders. Nothing is estimated or guessed.
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
