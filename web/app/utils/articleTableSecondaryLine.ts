import type { Article } from '~/composables/useArticles'

type ArticleTableRow = Pick<Article, 'title' | 'pokemon_name' | 'set_code' | 'card_number' | 'condition'>

/**
 * Short subtitle for article table rows. Set code and card number live in dedicated columns;
 * the full listing title is kept for search and tooltips only.
 */
export function articleTableSecondaryLine(row: ArticleTableRow): string {
  const title = row.title?.trim() ?? ''
  if (!title) {
    return ''
  }

  const parts: string[] = []

  const expansionMatch = title.match(/\s-\s([^-\n]+?)\s-\sPok[eé]mon(?:\s|$)/i)
  const expansion = expansionMatch?.[1]?.trim()
  if (expansion && expansion.length > 1) {
    parts.push(expansion)
  }

  const pokemon = row.pokemon_name?.trim()
  if (pokemon) {
    const frenchNameMatch = title.match(/^\s*([^/]+?)\s*\/\s*/)
    const french = frenchNameMatch?.[1]?.trim()
    if (
      french &&
      french.length > 1 &&
      french.toLowerCase() !== pokemon.toLowerCase() &&
      !pokemon.toLowerCase().includes(french.toLowerCase())
    ) {
      parts.unshift(french)
    }
  }

  const condition = row.condition?.trim()
  if (condition && condition !== 'Near Mint') {
    parts.push(condition)
  }

  return parts.join(' · ')
}
