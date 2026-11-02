/** Ids this page made for Conversations that the server does not hold yet, so nothing asks it about them. An id
 *  leaves the set with the first message, from then on the server knows the Conversation. A reload forgets the set,
 *  which only costs one request that answers 404 (new) or the stored messages. */
const fresh = new Set<string>()

export function newConversationId(): string {
  const id = crypto.randomUUID()
  fresh.add(id)
  return id
}

export const isNewConversation = (threadId: string) => fresh.has(threadId)

export const markStarted = (threadId: string) => void fresh.delete(threadId)
