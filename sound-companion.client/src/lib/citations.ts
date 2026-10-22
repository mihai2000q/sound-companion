import type { Citation } from '../types/chat'

const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** The `Title > Section` label the prompt makes the model write after a fact. A lead chunk has no section. */
export const labelOf = ({ title, section }: Citation) => (section ? `${title} > ${section}` : title)

/** One chip per cited label: the retrieved chunks whose label the answer text mentions. A lead chunk's bare title
 *  does not count when it only starts a longer label. The `url` always comes from the event, never from the text. */
export function chipsFor(text: string, citations: Citation[]): Citation[] {
  const chips = new Map<string, Citation>()
  for (const citation of citations) {
    const label = labelOf(citation)
    if (chips.has(label)) continue
    const pattern = new RegExp(escape(label) + (citation.section ? '' : '(?!\\s*>)'), 'i')
    if (pattern.test(text)) chips.set(label, citation)
  }
  return [...chips.values()]
}
