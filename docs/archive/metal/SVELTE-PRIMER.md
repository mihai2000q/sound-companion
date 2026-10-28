# Svelte 5 primer (just what this project needs)

Svelte is a compiler-based UI framework. You write components in `.svelte` files and the compiler turns them into small, fast JavaScript. SvelteKit adds routing, server endpoints and server-side rendering on top. Check the official docs (svelte.dev, svelte.dev/docs/kit) for exact syntax at the installed version.

## 1. A component

```svelte
<script lang="ts">
  let count = $state(0);
  let double = $derived(count * 2);
</script>

<button onclick={() => count++}>Clicked {count} times (double {double})</button>

<style>
  button { padding: 0.5rem 1rem; }
</style>
```

- `<script>` holds logic, markup follows, `<style>` is scoped to the component.
- `{expression}` puts a value in the markup.

## 2. Reactivity with runes

| Rune | Meaning |
|---|---|
| `$state(x)` | Reactive variable. Assigning to it updates the UI. |
| `$derived(expr)` | Value recomputed when the things it uses change. |
| `$effect(() => {...})` | Runs side effects after the DOM updates. Use sparingly. |
| `$props()` | Receives properties from the parent component. |

## 3. Props

```svelte
<!-- ToolCard.svelte -->
<script lang="ts">
  let { name, args, result, status } = $props();
</script>

<div class="collapse">
  <div class="collapse-title">{name} ({status})</div>
  ...
</div>
```

## 4. Markup logic

```svelte
{#each messages as m (m.id)}
  <ChatBubble {m} />
{/each}

{#if loading}
  <span class="loading loading-dots"></span>
{:else}
  <p>Ready</p>
{/if}
```

The `(m.id)` is a key so Svelte can track items.

## 5. Shared state

A `.svelte.ts` module can hold state used by several components:

```ts
// src/lib/stores/chat.svelte.ts
export const chat = $state({ messages: [], sources: [], usage: null, streaming: false });
```

Components import `chat` and read or mutate it directly.

## 6. Routing in SvelteKit

| File | Route |
|---|---|
| `src/routes/+page.svelte` | `/` (the chat page) |
| `src/routes/api/chat/+server.ts` | `POST /api/chat` (the SSE endpoint) |
| `src/routes/api/threads/+server.ts` | `/api/threads` (history) |

Server files (`+server.ts`, anything under `$lib/server`) never reach the browser, which is why the API key and LangChain code live there.

## 7. An SSE endpoint

```ts
// src/routes/api/chat/+server.ts
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ request }) => {
  const { threadId, message } = await request.json();
  const stream = new ReadableStream({
    async start(controller) {
      const enc = new TextEncoder();
      const send = (event: object) =>
        controller.enqueue(enc.encode(`data: ${JSON.stringify(event)}\n\n`));
      // run the agent, call send({ type: 'token', text }) as events arrive
      send({ type: 'done' });
      controller.close();
    }
  });
  return new Response(stream, {
    headers: { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' }
  });
};
```

Reading it in the browser:

```ts
const res = await fetch('/api/chat', { method: 'POST', body: JSON.stringify({ threadId, message }) });
const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
let buffer = '';
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += value;
  const parts = buffer.split('\n\n');
  buffer = parts.pop()!;
  for (const part of parts) handle(JSON.parse(part.replace(/^data: /, '')));
}
```

Add validation and error handling before real use. Check the current SvelteKit docs for the exact `RequestHandler` types.

## 8. shadcn/ui components you will use

`button`, `badge`, `collapsible`, `card`, `progress`, `alert`, `sheet`, `tabs` (there is no chat component, so bubbles are plain Tailwind). Themes switch with a `.dark` class on the root element (a dark theme suits this project). Confirm the Tailwind and shadcn/ui versions work together at setup.

## 9. Suggested components (about six)

`ChatPage`, `MessageList`, `MessageBubble`, `ToolCard`, `Inspector`, `Composer`.
