import { zVisualizationType, zChartVisualization } from './types'

describe('zVisualizationType: stats blocks', () => {
  it('accepts a well-formed stats block', () => {
    const block = {
      title: { en: 'Overview' },
      type: 'stats',
      tiles: [
        { label: { en: 'Total rows' }, aggregate: 'count' },
        { label: { en: 'Distinct platforms' }, aggregate: 'distinct', column: 'platform' }
      ]
    }
    expect(zVisualizationType.safeParse(block).success).toBe(true)
  })

  it('rejects a stats block with an unknown aggregate', () => {
    const block = {
      title: { en: 'Overview' },
      type: 'stats',
      tiles: [{ label: { en: 'Total' }, aggregate: 'median' }]
    }
    expect(zVisualizationType.safeParse(block).success).toBe(false)
  })

  it('rejects a stats block with no tiles', () => {
    const block = { title: { en: 'Overview' }, type: 'stats', tiles: [] }
    expect(zVisualizationType.safeParse(block).success).toBe(false)
  })

  it('rejects a stats block with a string label instead of a locale dict', () => {
    const block = {
      title: { en: 'Overview' },
      type: 'stats',
      tiles: [{ label: 'Total', aggregate: 'count' }]
    }
    expect(zVisualizationType.safeParse(block).success).toBe(false)
  })

  it('accepts a tile with no column when the aggregate is "count"', () => {
    const block = {
      title: { en: 'Overview' },
      type: 'stats',
      tiles: [{ label: { en: 'Total' }, aggregate: 'count' }]
    }
    expect(zVisualizationType.safeParse(block).success).toBe(true)
  })

  it.each(['distinct', 'min', 'max', 'sum', 'mean', 'first_date', 'last_date', 'span_days', 'busiest_day'] as const)(
    'rejects a tile with no column for aggregate "%s"',
    (aggregate) => {
      const block = {
        title: { en: 'Overview' },
        type: 'stats',
        tiles: [{ label: { en: 'Total' }, aggregate }]
      }
      expect(zVisualizationType.safeParse(block).success).toBe(false)
    }
  )
})

describe('zVisualizationType: heatmap blocks', () => {
  it('accepts a well-formed calendar heatmap block', () => {
    const block = { title: { en: 'Activity' }, type: 'heatmap', mode: 'calendar', dateColumn: 'created_at' }
    expect(zVisualizationType.safeParse(block).success).toBe(true)
  })

  it('accepts a well-formed weekday_hour heatmap block with valueColumn + aggregate', () => {
    const block = {
      title: { en: 'Activity' },
      type: 'heatmap',
      mode: 'weekday_hour',
      dateColumn: 'created_at',
      valueColumn: 'duration',
      aggregate: 'sum'
    }
    expect(zVisualizationType.safeParse(block).success).toBe(true)
  })

  it('rejects a heatmap block with an unknown mode', () => {
    const block = { title: { en: 'Activity' }, type: 'heatmap', mode: 'monthly', dateColumn: 'created_at' }
    expect(zVisualizationType.safeParse(block).success).toBe(false)
  })

  it('rejects a heatmap block missing dateColumn', () => {
    const block = { title: { en: 'Activity' }, type: 'heatmap', mode: 'calendar' }
    expect(zVisualizationType.safeParse(block).success).toBe(false)
  })

  it('rejects a heatmap block with an unsupported cell aggregate', () => {
    const block = {
      title: { en: 'Activity' }, type: 'heatmap', mode: 'calendar', dateColumn: 'created_at', aggregate: 'pct'
    }
    expect(zVisualizationType.safeParse(block).success).toBe(false)
  })
})

describe('zVisualizationType: thread blocks', () => {
  it('accepts a well-formed thread block with groupColumn', () => {
    const block = {
      title: { en: 'Your conversations' },
      type: 'thread',
      groupColumn: 'Conversation title',
      roleColumn: 'Role',
      textColumn: 'Message',
      timeColumn: 'Time',
      badgeColumn: 'Model',
      selfRole: 'user',
      pageSize: { threads: 20, turns: 50 }
    }
    expect(zVisualizationType.safeParse(block).success).toBe(true)
  })

  it('accepts a thread block with only the required fields', () => {
    const block = { title: { en: 'Chats' }, type: 'thread', groupColumn: 'group', roleColumn: 'role', textColumn: 'text' }
    expect(zVisualizationType.safeParse(block).success).toBe(true)
  })

  it('accepts a thread block with titleColumn alongside groupColumn', () => {
    const block = {
      title: { en: 'Chats' }, type: 'thread', groupColumn: 'Conversation id', titleColumn: 'Conversation title',
      roleColumn: 'role', textColumn: 'text'
    }
    expect(zVisualizationType.safeParse(block).success).toBe(true)
  })

  it('accepts singleThreadTitle in place of groupColumn (WhatsApp-style flat chat)', () => {
    const block = {
      title: { en: 'Your chat' },
      type: 'thread',
      singleThreadTitle: { en: 'The chat' },
      roleColumn: 'Name',
      textColumn: 'Message'
    }
    expect(zVisualizationType.safeParse(block).success).toBe(true)
  })

  it('rejects a thread block with neither groupColumn nor singleThreadTitle', () => {
    const block = { title: { en: 'Chats' }, type: 'thread', roleColumn: 'role', textColumn: 'text' }
    expect(zVisualizationType.safeParse(block).success).toBe(false)
  })

  it('rejects a thread block missing roleColumn', () => {
    const block = { title: { en: 'Chats' }, type: 'thread', groupColumn: 'group', textColumn: 'text' }
    expect(zVisualizationType.safeParse(block).success).toBe(false)
  })

  it('rejects a thread block missing textColumn', () => {
    const block = { title: { en: 'Chats' }, type: 'thread', groupColumn: 'group', roleColumn: 'role' }
    expect(zVisualizationType.safeParse(block).success).toBe(false)
  })

  it('rejects a non-integer or non-positive pageSize value', () => {
    const block = {
      title: { en: 'Chats' }, type: 'thread', groupColumn: 'group', roleColumn: 'role', textColumn: 'text',
      pageSize: { threads: 0 }
    }
    expect(zVisualizationType.safeParse(block).success).toBe(false)
  })
})

describe('zChartVisualization: group.top', () => {
  it('accepts a numeric top', () => {
    const block = {
      title: { en: 'Top categories' },
      type: 'bar',
      group: { column: 'category', top: 5 },
      values: [{ column: '.COUNT' }]
    }
    expect(zChartVisualization.safeParse(block).success).toBe(true)
  })

  it('is optional (existing charts without top keep validating)', () => {
    const block = {
      title: { en: 'Categories' },
      type: 'bar',
      group: { column: 'category' },
      values: [{ column: '.COUNT' }]
    }
    expect(zChartVisualization.safeParse(block).success).toBe(true)
  })

  it('rejects a non-numeric top', () => {
    const block = {
      title: { en: 'Top categories' },
      type: 'bar',
      group: { column: 'category', top: 'five' },
      values: [{ column: '.COUNT' }]
    }
    expect(zChartVisualization.safeParse(block).success).toBe(false)
  })

  it.each([0, -1, 2.5])('rejects top: %s (must be a positive integer)', (top) => {
    const block = {
      title: { en: 'Top categories' },
      type: 'bar',
      group: { column: 'category', top },
      values: [{ column: '.COUNT' }]
    }
    expect(zChartVisualization.safeParse(block).success).toBe(false)
  })
})
