import { createContext, useContext } from 'react'

/** Whether an answer is streaming. The Conversations list lives in the shell around every page, so it learns this from here. */
export interface ChatActivity {
  streaming: boolean
  setStreaming: (streaming: boolean) => void
}

export const ChatActivityContext = createContext<ChatActivity>({ streaming: false, setStreaming: () => {} })

export function useChatActivity() {
  return useContext(ChatActivityContext)
}
