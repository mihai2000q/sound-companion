import { createContext, useContext } from 'react'

/** State the shell around every page keeps, so it survives a switch of Conversation or page: whether an answer is
 *  streaming (the Conversations list waits for it) and whether the Inspector is open. */
export interface ChatActivity {
  streaming: boolean
  setStreaming: (streaming: boolean) => void
  inspectorOpen: boolean
  setInspectorOpen: (open: boolean) => void
}

export const ChatActivityContext = createContext<ChatActivity>({ streaming: false, setStreaming: () => {}, inspectorOpen: false, setInspectorOpen: () => {} })

export function useChatActivity() {
  return useContext(ChatActivityContext)
}
