import { prepareThreadData } from './prepareThreadData'
import { Table, ThreadVisualization } from '../types'

function makeTable (rows: Array<[string, string, string, string?, string?]>, columns: string[] = ['group', 'role', 'text', 'time', 'badge']): Table {
  return {
    id: 't1',
    head: { cells: columns },
    body: { rows: rows.map((cells, i) => ({ id: String(i), cells: cells.filter((c) => c !== undefined) as string[] })) }
  }
}

const baseViz: ThreadVisualization = {
  title: {},
  type: 'thread',
  groupColumn: 'group',
  roleColumn: 'role',
  textColumn: 'text',
  timeColumn: 'time',
  badgeColumn: 'badge'
}

describe('prepareThreadData: empty table', () => {
  it('returns no threads for an empty table', async () => {
    const result = await prepareThreadData(makeTable([]), baseViz)
    expect(result.threads).toEqual([])
    expect(result.truncated).toBe(false)
  })

  it('resolves pageSize defaults when omitted', async () => {
    const result = await prepareThreadData(makeTable([]), baseViz)
    expect(result.pageSize).toEqual({ threads: 20, turns: 50 })
  })

  it('applies configured pageSize overrides', async () => {
    const result = await prepareThreadData(makeTable([]), { ...baseViz, pageSize: { threads: 5, turns: 10 } })
    expect(result.pageSize).toEqual({ threads: 5, turns: 10 })
  })

  it('carries selfRole through unchanged (undefined stays undefined)', async () => {
    const withSelf = await prepareThreadData(makeTable([]), { ...baseViz, selfRole: 'user' })
    expect(withSelf.selfRole).toBe('user')
    const withoutSelf = await prepareThreadData(makeTable([]), baseViz)
    expect(withoutSelf.selfRole).toBeUndefined()
  })
})

describe('prepareThreadData: grouping and ordering', () => {
  it('groups rows by groupColumn, preserving first-appearance order across threads', async () => {
    const table = makeTable([
      ['Conversation B', 'user', 'b1', '2024-01-02T00:00:00.000Z'],
      ['Conversation A', 'user', 'a1', '2024-01-01T00:00:00.000Z'],
      ['Conversation B', 'assistant', 'b2', '2024-01-02T00:05:00.000Z'],
      ['Conversation A', 'assistant', 'a2', '2024-01-01T00:05:00.000Z']
    ])
    const result = await prepareThreadData(table, baseViz)
    expect(result.threads.map((t) => t.title)).toEqual(['Conversation B', 'Conversation A'])
    expect(result.threads[0].count).toBe(2)
    expect(result.threads[1].count).toBe(2)
  })

  it('gives each thread a unique id and includes role/text/badge on each turn', async () => {
    const table = makeTable([
      ['A', 'user', 'hello', '2024-01-01T00:00:00.000Z', 'gpt-test'],
      ['A', 'assistant', 'hi there', '2024-01-01T00:01:00.000Z', 'gpt-test']
    ])
    const result = await prepareThreadData(table, baseViz)
    expect(result.threads).toHaveLength(1)
    const [thread] = result.threads
    expect(thread.id).toBe('0')
    expect(thread.turns).toEqual([
      { role: 'user', text: 'hello', time: '2024-01-01T00:00:00.000Z', badge: 'gpt-test' },
      { role: 'assistant', text: 'hi there', time: '2024-01-01T00:01:00.000Z', badge: 'gpt-test' }
    ])
  })

  it('sorts turns within a thread by time when timeColumn parses, regardless of row order', async () => {
    const table = makeTable([
      ['A', 'assistant', 'second', '2024-01-01T10:00:00.000Z'],
      ['A', 'user', 'first', '2024-01-01T09:00:00.000Z']
    ])
    const result = await prepareThreadData(table, baseViz)
    expect(result.threads[0].turns.map((t) => t.text)).toEqual(['first', 'second'])
  })

  it('sets firstTime/lastTime to the min/max parsed time in the thread', async () => {
    const table = makeTable([
      ['A', 'user', 'first', '2024-01-01T09:00:00.000Z'],
      ['A', 'assistant', 'second', '2024-01-03T09:00:00.000Z'],
      ['A', 'user', 'third', '2024-01-02T09:00:00.000Z']
    ])
    const result = await prepareThreadData(table, baseViz)
    expect(result.threads[0].firstTime).toBe('2024-01-01T09:00:00.000Z')
    expect(result.threads[0].lastTime).toBe('2024-01-03T09:00:00.000Z')
  })

  it('leaves a turn with no badge cell (empty string) without a badge field', async () => {
    const table = makeTable([['A', 'user', 'hello', '2024-01-01T00:00:00.000Z', '']])
    const result = await prepareThreadData(table, baseViz)
    expect(result.threads[0].turns[0].badge).toBeUndefined()
  })
})

describe('prepareThreadData: missing time column', () => {
  const noTimeViz: ThreadVisualization = { title: {}, type: 'thread', groupColumn: 'group', roleColumn: 'role', textColumn: 'text' }

  it('keeps rows in original order and omits time/firstTime/lastTime when timeColumn is not configured', async () => {
    const table = makeTable([
      ['A', 'assistant', 'second'],
      ['A', 'user', 'first']
    ], ['group', 'role', 'text'])
    const result = await prepareThreadData(table, noTimeViz)
    expect(result.threads[0].turns.map((t) => t.text)).toEqual(['second', 'first'])
    expect(result.threads[0].turns[0].time).toBeUndefined()
    expect(result.threads[0].firstTime).toBeUndefined()
    expect(result.threads[0].lastTime).toBeUndefined()
  })

  it('sorts parseable rows before unparseable rows, which keep their relative order', async () => {
    const table = makeTable([
      ['A', 'user', 'no-date-1', 'not-a-date'],
      ['A', 'user', 'dated', '2024-01-01T00:00:00.000Z'],
      ['A', 'user', 'no-date-2', 'also-not-a-date']
    ])
    const result = await prepareThreadData(table, baseViz)
    expect(result.threads[0].turns.map((t) => t.text)).toEqual(['dated', 'no-date-1', 'no-date-2'])
  })
})

describe('prepareThreadData: single-thread mode (singleThreadTitle)', () => {
  it('puts every row into one thread titled by singleThreadTitle when groupColumn is absent', async () => {
    const table = makeTable([
      ['ignored', 'Alice', 'hi', '2024-01-01T00:00:00.000Z'],
      ['ignored', 'Bob', 'hello', '2024-01-01T00:01:00.000Z']
    ], ['group', 'role', 'text', 'time'])
    const viz: ThreadVisualization = {
      title: {}, type: 'thread', singleThreadTitle: { en: 'The chat' }, roleColumn: 'role', textColumn: 'text', timeColumn: 'time'
    }
    const result = await prepareThreadData(table, viz)
    expect(result.threads).toHaveLength(1)
    expect(result.threads[0].title).toEqual({ en: 'The chat' })
    expect(result.threads[0].count).toBe(2)
  })
})

describe('prepareThreadData: titleColumn (grouping key distinct from displayed title)', () => {
  function makeIdTitleTable (rows: Array<[string, string, string, string]>): Table {
    // columns: id, title, role, text -- groupColumn is 'id' (unique per
    // conversation), titleColumn is 'title' (can repeat across conversations).
    return {
      id: 't1',
      head: { cells: ['id', 'title', 'role', 'text'] },
      body: { rows: rows.map((cells, i) => ({ id: String(i), cells })) }
    }
  }

  it('two conversations with identical titles but distinct groupColumn ids yield two threads', async () => {
    const table = makeIdTitleTable([
      ['conv-x', 'Duplicate title', 'user', 'hello from x'],
      ['conv-x', 'Duplicate title', 'assistant', 'hi there x'],
      ['conv-y', 'Duplicate title', 'user', 'hello from y']
    ])
    const viz: ThreadVisualization = {
      title: {}, type: 'thread', groupColumn: 'id', titleColumn: 'title', roleColumn: 'role', textColumn: 'text'
    }
    const result = await prepareThreadData(table, viz)
    expect(result.threads).toHaveLength(2)
    expect(result.threads.map((t) => t.title)).toEqual(['Duplicate title', 'Duplicate title'])
    expect(result.threads.map((t) => t.count)).toEqual([2, 1])
  })

  it('falls back to groupColumn itself as the title when titleColumn is not given', async () => {
    const table = makeIdTitleTable([['conv-x', 'Duplicate title', 'user', 'hello']])
    const viz: ThreadVisualization = { title: {}, type: 'thread', groupColumn: 'id', roleColumn: 'role', textColumn: 'text' }
    const result = await prepareThreadData(table, viz)
    expect(result.threads[0].title).toBe('conv-x')
  })
})

describe('prepareThreadData: cap at 5000 threads', () => {
  it('truncates beyond 5000 groups and sets the truncation flag', async () => {
    const rows: Array<[string, string, string]> = []
    for (let i = 0; i < 5010; i++) rows.push([`group-${i}`, 'user', 'hi'])
    const table = makeTable(rows, ['group', 'role', 'text'])
    const viz: ThreadVisualization = { title: {}, type: 'thread', groupColumn: 'group', roleColumn: 'role', textColumn: 'text' }
    const result = await prepareThreadData(table, viz)
    expect(result.threads).toHaveLength(5000)
    expect(result.truncated).toBe(true)
    expect(result.totalThreads).toBe(5010)
  })

  it('does not truncate at exactly 5000 groups', async () => {
    const rows: Array<[string, string, string]> = []
    for (let i = 0; i < 5000; i++) rows.push([`group-${i}`, 'user', 'hi'])
    const table = makeTable(rows, ['group', 'role', 'text'])
    const viz: ThreadVisualization = { title: {}, type: 'thread', groupColumn: 'group', roleColumn: 'role', textColumn: 'text' }
    const result = await prepareThreadData(table, viz)
    expect(result.threads).toHaveLength(5000)
    expect(result.truncated).toBe(false)
    expect(result.totalThreads).toBe(5000)
  })
})
