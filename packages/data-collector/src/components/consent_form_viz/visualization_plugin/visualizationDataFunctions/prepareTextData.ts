import { extractUrlDomain, getTableColumn, tokenize } from './util'
import { TextVisualizationData, TextVisualization, ScoredTerm, Table } from '../types'

interface VocabularyStats {
  value: number
  docFreq: number
}

// Media-placeholder text a chat export substitutes for an attachment, in the
// bracketed form WhatsApp actually writes ("<Media omitted>",
// "<Media weggelaten>") and the bare form some export variants use instead.
// Exported so the list can grow without touching the strip logic below.
export const PLACEHOLDER_PHRASES = [
  'Media omitted',
  'image omitted',
  'video omitted',
  'audio omitted',
  'sticker omitted',
  'GIF omitted',
  'document omitted',
  'Media weggelaten',
  'Bijlage weggelaten',
  'afbeelding weggelaten',
  'video weggelaten',
  'audio weggelaten',
  'sticker weggelaten',
  'document weggelaten',
]

// Matches a whole <...> tag (any content, e.g. "<Media weggelaten>" or
// "<attached: photo.jpg>") or one of PLACEHOLDER_PHRASES on its own -- built
// once per module load, not per row.
const PLACEHOLDER_PATTERN = new RegExp(
  ['<[^>]*>', ...PLACEHOLDER_PHRASES.map(escapeRegExp)].join('|'),
  'gi'
)

function escapeRegExp (text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// Pre-tokenize cleanup: strip placeholder text so it can never itself become
// a "term" (e.g. tokenize:false, or a stray bracketed tag no whitespace
// splits away). Replaces with a space, not '', so words on either side of a
// removed placeholder never fuse into one token.
function stripPlaceholders (text: string): string {
  return text.replace(PLACEHOLDER_PATTERN, ' ')
}

// Every distinct value of excludeColumn, lowercased and split on whitespace
// -- for a chat table (excludeColumn: participant-name column) this turns
// "John Doe" into the stopwords "john" and "doe".
function buildExcludeSet (table: Table, excludeColumn: string | undefined): Set<string> {
  const excludeSet = new Set<string>()
  if (excludeColumn === undefined) return excludeSet
  for (const value of getTableColumn(table, excludeColumn)) {
    for (const word of value.toLowerCase().split(/\s+/)) {
      if (word !== '') excludeSet.add(word)
    }
  }
  return excludeSet
}

export async function prepareTextData (table: Table, visualization: TextVisualization): Promise<TextVisualizationData> {
  const visualizationData: TextVisualizationData = {
    type: visualization.type,
    topTerms: []
  }

  if (table.body.rows.length === 0) return visualizationData

  const texts = getTableColumn(table, visualization.textColumn)
  const values = visualization.valueColumn != null ? getTableColumn(table, visualization.valueColumn) : null
  const excludeSet = buildExcludeSet(table, visualization.excludeColumn)

  const vocabulary = getVocabulary(texts, values, visualization, excludeSet)
  visualizationData.topTerms = getTopTerms(vocabulary, texts.length, 200)

  return visualizationData
}

function getVocabulary (
  texts: string[],
  values: string[] | null,
  visualization: TextVisualization,
  excludeSet: Set<string>
): Record<string, VocabularyStats> {
  const vocabulary: Record<string, VocabularyStats> = {}

  for (let i = 0; i < texts.length; i++) {
    if (texts?.[i] == null) continue
    const text = visualization.stripPlaceholders === true ? stripPlaceholders(texts[i]) : texts[i]
    const tokens = visualization.tokenize != null && visualization.tokenize ? tokenize(text) : [text]

    const seen = new Set<string>()
    for (let token of tokens) {
      if (token.trim() === '') continue
      if (visualization.stripMentions === true && token.startsWith('@')) continue
      if (excludeSet.has(token.toLowerCase())) continue

      if (visualization.extract === 'url_domain') token = extractUrlDomain(token)
      if (vocabulary[token] === undefined) vocabulary[token] = { value: 0, docFreq: 0 }
      if (!seen.has(token)) {
        vocabulary[token].docFreq += 1
        seen.add(token)
      }

      // Number() never returns null/undefined (only NaN for unparsable input), so
      // `Number(values[i]) ?? 1` never actually falls back to the intended weight of
      // 1 -- combined with the isNaN guard below, a non-numeric cell silently
      // contributed 0 instead. Guard against NaN explicitly instead.
      let v = 1
      if (values != null) {
        const numericValue = Number(values[i])
        v = Number.isNaN(numericValue) ? 1 : numericValue
      }
      vocabulary[token].value += v
    }
  }
  return vocabulary
}

function getTopTerms (vocabulary: Record<string, VocabularyStats>, nDocs: number, topTerms: number): ScoredTerm[] {
  return Object.entries(vocabulary)
    .map(([text, stats]) => {
      const tf = stats.value
      const idf = Math.log(nDocs / stats.docFreq)
      return { text, value: stats.value, importance: tf * idf }
    })
    .sort((a, b) => b.importance - a.importance)
    .slice(0, topTerms)
}
