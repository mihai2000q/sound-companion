import type { ChatMessage, ToolCall } from '../types/chat'
import type { StoredMessage, StoredToolCall } from '../types/threads'
import { isToolError } from './toolResult'

/** The text the server puts in front of a tool call whose run was stopped (`CANCELLED` in streaming.py). */
const CANCELLED = 'This tool call was cancelled before it finished, so there is no result.'

function toolCallOf(call: StoredToolCall): ToolCall {
  const status = call.result === null || call.result === CANCELLED ? 'stopped' : isToolError(call.result) ? 'error' : 'done'
  return { id: call.id, name: call.name, args: call.args, status, content: call.result ?? undefined }
}

/** A stored Conversation as the chat's messages: one user message, then one bot message for the whole turn (every
 *  assistant step of it, as when streamed). The queries of a search are not stored, so a restored turn has none.
 *  Ids are made from the position, and chunks get an id of their own because the stored Citations have none. */
export function toChatMessages(stored: StoredMessage[]): ChatMessage[] {
  const out: ChatMessage[] = []
  stored.forEach((message, i) => {
    if (message.role === 'user') {
      out.push({ id: `restored-${i}`, role: 'user', text: message.text })
      out.push({ id: `restored-${i}-answer`, role: 'bot', text: '' })
      return
    }
    const bot = out.at(-1)
    if (!bot || bot.role !== 'bot') return
    const calls = (message.tool_calls ?? []).map(toolCallOf)
    const citations = (message.tool_calls ?? []).flatMap((call) => call.citations)
    out[out.length - 1] = {
      ...bot,
      text: [bot.text, message.text].filter(Boolean).join('\n\n'),
      toolCalls: calls.length ? [...(bot.toolCalls ?? []), ...calls] : bot.toolCalls,
      citations: citations.length
        ? [...(bot.citations ?? []), ...citations.map((c, n) => ({ ...c, id: `${bot.id}-chunk-${(bot.citations?.length ?? 0) + n}` }))]
        : bot.citations,
    }
  })
  return out
}
