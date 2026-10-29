import type { ChatMessage } from '../types/chat'

/** What the bot is doing right now, in words, from the events already received (`queries`, `tool_call`, `tool_result`).
 *  `null` once the answer text is flowing, there is nothing to say then. */
export function stageOf(message: ChatMessage): string | null {
  if (message.text !== '') return null
  const running = message.toolCalls?.findLast((call) => call.status === 'running')
  if (running) {
    if (running.name === 'search_knowledge_base') {
      const queries = message.queries
      return queries?.length ? `Searching: ${queries.join(' · ')}` : 'Searching the sources'
    }
    return `Calling ${running.name}`
  }
  return message.toolCalls?.length ? 'Writing the answer' : 'Thinking'
}
