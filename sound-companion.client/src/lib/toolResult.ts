/** The music tools return `{ error, message }` for bad input, inside <tool_result tool="...">...</tool_result>. */
export function isToolError(content: string): boolean {
  const body = content.match(/^<tool_result tool="[^"]*">\n([\s\S]*)\n<\/tool_result>$/)?.[1] ?? content
  try {
    const parsed = JSON.parse(body)
    return typeof parsed?.error === 'string' && typeof parsed?.message === 'string'
  } catch {
    return false
  }
}
