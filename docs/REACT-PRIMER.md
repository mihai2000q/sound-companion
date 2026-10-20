# React primer (the parts this project uses)

A quick reference for the frontend (`frontend/`: Vite, React, TypeScript, Tailwind + DaisyUI). It is not a full tutorial. Check the official React and Vite docs for exact syntax at the installed versions, which are not yet pinned (story 1).

## 1. A component

```tsx
type ToolCardProps = { name: string; args: unknown; result?: string; status: 'running' | 'done' | 'error' };

export function ToolCard({ name, args, result, status }: ToolCardProps) {
  return (
    <div className="collapse collapse-arrow bg-base-200">
      <input type="checkbox" />
      <div className="collapse-title font-medium">
        {name} {status === 'running' && <span className="loading loading-spinner loading-xs" />}
      </div>
      <div className="collapse-content">
        <pre>{JSON.stringify(args, null, 2)}</pre>
        {result && <p>{result}</p>}
      </div>
    </div>
  );
}
```

- A component is a function that takes props and returns markup (JSX).
- `{expression}` puts a value in the markup. React escapes text by default, so never use `dangerouslySetInnerHTML` for model output.

## 2. State

```tsx
const [input, setInput] = useState('');
```

- `useState` holds a value that, when set, re-renders the component.
- For the conversation, keep one object (`messages`, `citations`, `toolCalls`, `usage`, `streaming`) in a single state or a `useReducer`. Each SSE event becomes a reducer action, which keeps the update logic in one place and easy to test.

## 3. Lists

```tsx
{messages.map(m => <MessageBubble key={m.id} message={m} />)}
```

Always give a stable `key` (the message id), not the array index.

## 4. Effects and refs

- `useEffect(() => { ... }, [deps])` runs code after render. Use it for things like scrolling to the bottom when messages change. Avoid it for logic that belongs in event handlers.
- `useRef` keeps a value that does not trigger re-renders, such as the `AbortController` of the current stream.

## 5. A streaming hook

```ts
export function useChatStream() {
  const abortRef = useRef<AbortController | null>(null);

  async function send(threadId: string, message: string, onEvent: (e: ChatEvent) => void) {
    abortRef.current = new AbortController();
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ thread_id: threadId, message }),
      signal: abortRef.current.signal,
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      const parts = buffer.split('\n\n');
      buffer = parts.pop() ?? '';
      for (const part of parts) {
        if (part.startsWith(':')) continue;                 // keepalive comment
        onEvent(JSON.parse(part.replace(/^data: /, '')));
      }
    }
  }

  const cancel = () => abortRef.current?.abort();
  return { send, cancel };
}
```

- `EventSource` only supports GET, so use `fetch` with a stream reader (a small library such as `@microsoft/fetch-event-source` is an alternative, not yet evaluated).
- Add error handling (a failed parse, a dropped connection) before real use.

## 6. The typed events

`frontend/src/types/events.ts` mirrors the events in [ARCHITECTURE.md](ARCHITECTURE.md#streaming-events-sse):

```ts
export type ChatEvent =
  | { type: 'token'; text: string }
  | { type: 'tool_call'; id: string; name: string; args: unknown }
  | { type: 'tool_result'; id: string; name: string; content: string; durationMs?: number }
  | { type: 'citations'; items: Citation[] }
  | { type: 'queries'; items: string[] }
  | { type: 'progress'; message: string }
  | { type: 'usage'; promptTokens: number; completionTokens: number; cost: number; totalSpend: number }
  | { type: 'error'; code: string; message: string }
  | { type: 'done' };
```

A reducer switches on `type`, and TypeScript checks every case is handled.

## 7. Vite dev proxy

```ts
// vite.config.ts
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
});
```

The browser only talks to its own origin, so no CORS setup is needed in development.

## 8. DaisyUI classes you will use

`chat chat-start chat-end chat-bubble`, `btn`, `badge`, `collapse`, `card`, `loading`, `progress`, `alert`, `drawer`, `tabs`. Themes switch with `data-theme="..."` on the root element. Confirm the Tailwind and DaisyUI versions work together at setup (`@plugin "daisyui"` in the CSS).

## 9. Suggested components (about six)

`App` (layout), `Chat`, `MessageBubble`, `ToolCard`, `Inspector`, `Composer`.
