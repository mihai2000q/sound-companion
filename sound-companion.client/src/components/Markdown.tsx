import ReactMarkdown, { type Components, type ExtraProps } from 'react-markdown'

/** An element with the chat's classes. react-markdown hands every component its syntax `node`, which must not reach the DOM. */
function styled<Tag extends 'p' | 'ol' | 'ul' | 'strong' | 'code'>(Tag: Tag, className: string) {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  return ({ node, ...props }: React.ComponentProps<Tag> & ExtraProps) => {
    const Element = Tag as React.ElementType
    return <Element className={className} {...props} />
  }
}

/** Raw HTML in the text is escaped (react-markdown's default), and links with an unsafe scheme lose their href. */
const components: Components = {
  p: styled('p', 'my-2 first:mt-0 last:mb-0'),
  ol: styled('ol', 'my-2 list-decimal space-y-1 pl-6'),
  ul: styled('ul', 'my-2 list-disc space-y-1 pl-6'),
  strong: styled('strong', 'font-semibold'),
  code: styled('code', 'rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]'),
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  a: ({ node, ...props }) => (
    <a className="underline underline-offset-2 hover:text-brass" target="_blank" rel="noopener noreferrer" {...props} />
  ),
}

/** The bot's answer as Markdown: bold, lists and links, styled to sit in the serif message text. */
export function Markdown({ children }: { children: string }) {
  return <ReactMarkdown components={components}>{children}</ReactMarkdown>
}
