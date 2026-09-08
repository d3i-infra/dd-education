import { prepareTextData, PLACEHOLDER_PHRASES } from './prepareTextData'
import { Table, TextVisualization } from '../types'

function makeTable (rows: Array<[string, string]>): Table {
  return {
    id: 't1',
    head: { cells: ['text', 'weight'] },
    body: {
      rows: rows.map(([text, weight], i) => ({ id: String(i), cells: [text, weight] }))
    }
  }
}

function makeChatTable (rows: Array<[string, string]>): Table {
  // A WhatsApp-shaped table: message text + the sender name column
  // excludeColumn reads from.
  return {
    id: 'chat',
    head: { cells: ['Message', 'Name'] },
    body: {
      rows: rows.map(([message, name], i) => ({ id: String(i), cells: [message, name] }))
    }
  }
}

// Pins the fix for the no-constant-binary-expression lint finding at
// prepareTextData.ts:47: `Number(values[i]) ?? 1` never falls back to 1,
// because Number() never returns null/undefined (only NaN for unparsable
// input). Combined with the `if (!isNaN(v))` guard just below, a non-numeric
// weight silently contributed 0 instead of the intended fallback weight 1.
describe('prepareTextData non-numeric value handling', () => {
  it('falls back to a weight of 1 for a non-numeric value cell', async () => {
    const table = makeTable([
      ['alpha', '3'],
      ['beta', 'not-a-number']
    ])
    const visualization: TextVisualization = {
      title: {},
      type: 'wordcloud',
      textColumn: 'text',
      valueColumn: 'weight'
    }

    const result = await prepareTextData(table, visualization)
    const alpha = result.topTerms.find((t) => t.text === 'alpha')
    const beta = result.topTerms.find((t) => t.text === 'beta')

    expect(alpha?.value).toBe(3)
    expect(beta?.value).toBe(1)
  })
})

describe('prepareTextData stripMentions', () => {
  it('drops tokens beginning with @ when stripMentions is true', async () => {
    const table = makeChatTable([
      ['@John hi there', 'Alice'],
      ['no mention here', 'Bob']
    ])
    const visualization: TextVisualization = {
      title: {}, type: 'wordcloud', textColumn: 'Message', tokenize: true, stripMentions: true
    }
    const result = await prepareTextData(table, visualization)
    expect(result.topTerms.some((t) => t.text === '@John')).toBe(false)
    expect(result.topTerms.some((t) => t.text === 'hi')).toBe(true)
  })

  it('keeps @-prefixed tokens when stripMentions is unset (default off)', async () => {
    const table = makeChatTable([['@John hi there', 'Alice']])
    const visualization: TextVisualization = { title: {}, type: 'wordcloud', textColumn: 'Message', tokenize: true }
    const result = await prepareTextData(table, visualization)
    expect(result.topTerms.some((t) => t.text === '@John')).toBe(true)
  })
})

describe('prepareTextData excludeColumn', () => {
  it('excludes every whitespace-split, lowercased word from the named column, case-insensitively', async () => {
    const table = makeChatTable([
      ['John said hello to everyone', 'John Doe'],
      ['Doe replied with a greeting', 'Jane Roe']
    ])
    const visualization: TextVisualization = {
      title: {}, type: 'wordcloud', textColumn: 'Message', tokenize: true, excludeColumn: 'Name'
    }
    const result = await prepareTextData(table, visualization)
    const terms = result.topTerms.map((t) => t.text)
    // 'John' and 'Doe' are excluded (from 'John Doe'); 'Jane' and 'Roe' never
    // appear in the message text so their absence proves nothing on its own,
    // but 'hello' and 'greeting' -- ordinary words -- must survive.
    expect(terms).not.toContain('John')
    expect(terms).not.toContain('Doe')
    expect(terms).toContain('hello')
    expect(terms).toContain('greeting')
  })

  it('does not exclude anything when excludeColumn is unset', async () => {
    const table = makeChatTable([['John said hello', 'John Doe']])
    const visualization: TextVisualization = { title: {}, type: 'wordcloud', textColumn: 'Message', tokenize: true }
    const result = await prepareTextData(table, visualization)
    expect(result.topTerms.some((t) => t.text === 'John')).toBe(true)
  })
})

describe('prepareTextData stripPlaceholders', () => {
  it('strips a bracketed placeholder in Dutch before tokenizing', async () => {
    const table = makeTable([
      ['<Media weggelaten>', ''],
      ['hoi allemaal', '']
    ])
    const visualization: TextVisualization = { title: {}, type: 'wordcloud', textColumn: 'text', tokenize: true, stripPlaceholders: true }
    const result = await prepareTextData(table, visualization)
    const terms = result.topTerms.map((t) => t.text)
    expect(terms).not.toContain('Media')
    expect(terms).not.toContain('weggelaten')
    expect(terms).toContain('hoi')
  })

  it('strips a bracketed placeholder in English before tokenizing', async () => {
    const table = makeTable([
      ['<Media omitted>', ''],
      ['hi everyone', '']
    ])
    const visualization: TextVisualization = { title: {}, type: 'wordcloud', textColumn: 'text', tokenize: true, stripPlaceholders: true }
    const result = await prepareTextData(table, visualization)
    const terms = result.topTerms.map((t) => t.text)
    expect(terms).not.toContain('Media')
    expect(terms).not.toContain('omitted')
    expect(terms).toContain('everyone')
  })

  it('strips every known bare-form phrase (no angle brackets) case-insensitively', async () => {
    for (const phrase of PLACEHOLDER_PHRASES) {
      const table = makeTable([[`before ${phrase} after`, '']])
      const visualization: TextVisualization = { title: {}, type: 'wordcloud', textColumn: 'text', tokenize: true, stripPlaceholders: true }
      const result = await prepareTextData(table, visualization)
      const terms = result.topTerms.map((t) => t.text)
      expect(terms).toContain('before')
      expect(terms).toContain('after')
      for (const word of phrase.split(' ')) expect(terms).not.toContain(word)
    }
  })

  it('strips an arbitrary bracketed tag, not just the known phrases', async () => {
    const table = makeTable([['<attached: photo.jpg> nice shot', '']])
    const visualization: TextVisualization = { title: {}, type: 'wordcloud', textColumn: 'text', tokenize: true, stripPlaceholders: true }
    const result = await prepareTextData(table, visualization)
    const terms = result.topTerms.map((t) => t.text)
    expect(terms).not.toContain('attached:')
    expect(terms).toContain('nice')
    expect(terms).toContain('shot')
  })

  it('leaves placeholder text intact when stripPlaceholders is unset', async () => {
    const table = makeTable([['<Media omitted>', '']])
    const visualization: TextVisualization = { title: {}, type: 'wordcloud', textColumn: 'text', tokenize: true }
    const result = await prepareTextData(table, visualization)
    // tokenize() splits on plain whitespace only, so the bracket stays
    // attached to the word -- the point here is only that stripPlaceholders
    // being unset performs no removal at all.
    expect(result.topTerms.some((t) => t.text.includes('Media'))).toBe(true)
  })
})
