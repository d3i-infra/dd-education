import { prepareStatsData } from './prepareStatsData'
import { Table, StatsVisualization, StatTile } from '../types'

// Mirrors util.ts formatDate's "day" formatter exactly, so date-value
// assertions below don't hardcode an English month abbreviation and stay
// correct under any ICU default locale (see formatDate.test.ts).
function expectedDay (iso: string): string {
  const date = new Date(iso)
  const year = date.getFullYear().toString()
  const month = new Intl.DateTimeFormat('default', { month: 'short' }).format(date)
  const day = date.getDate().toString()
  return `${year}-${month}-${day}`
}

// A synthetic table of "sessions": a date column, a numeric duration column,
// and a categorical platform column. Two rows share a calendar day (the 3rd)
// so busiest_day has an unambiguous winner.
function makeTable (): Table {
  const rows: Array<[string, string, string]> = [
    ['2024-01-01T09:00:00.000Z', '10', 'a'],
    ['2024-01-03T09:00:00.000Z', '20', 'b'],
    ['2024-01-03T15:00:00.000Z', '30', 'a'],
    ['2024-01-05T09:00:00.000Z', '', 'b'] // blank duration -- exercises the non-numeric guard
  ]
  return {
    id: 't1',
    head: { cells: ['date', 'duration', 'platform'] },
    body: { rows: rows.map(([date, duration, platform], i) => ({ id: String(i), cells: [date, duration, platform] })) }
  }
}

function tileFor (aggregate: StatTile['aggregate'], column?: string, dateFormat?: StatTile['dateFormat']): StatsVisualization {
  return {
    title: {},
    type: 'stats',
    tiles: [{ label: { en: 'label' }, aggregate, column, dateFormat }]
  }
}

describe('prepareStatsData', () => {
  it('count: total row count, ignoring column', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('count'))
    expect(result.tiles[0].value).toBe('4')
  })

  it('count: counts only non-empty cells when a column is given', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('count', 'duration'))
    expect(result.tiles[0].value).toBe('3')
  })

  it('distinct: counts distinct non-empty values in a column', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('distinct', 'platform'))
    expect(result.tiles[0].value).toBe('2')
  })

  it('min: smallest numeric value, ignoring non-numeric cells', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('min', 'duration'))
    expect(result.tiles[0].value).toBe('10')
  })

  it('max: largest numeric value', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('max', 'duration'))
    expect(result.tiles[0].value).toBe('30')
  })

  it('sum: total of numeric values', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('sum', 'duration'))
    expect(result.tiles[0].value).toBe('60')
  })

  it('mean: average of numeric values', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('mean', 'duration'))
    expect(result.tiles[0].value).toBe('20')
  })

  it('first_date: earliest date, formatted at day precision by default', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('first_date', 'date'))
    expect(result.tiles[0].value).toBe(expectedDay('2024-01-01T09:00:00.000Z'))
  })

  it('last_date: latest date', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('last_date', 'date'))
    expect(result.tiles[0].value).toBe(expectedDay('2024-01-05T09:00:00.000Z'))
  })

  it('first_date/last_date respect an explicit dateFormat', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('first_date', 'date', 'year'))
    expect(result.tiles[0].value).toBe('2024')
  })

  it('span_days: whole days between earliest and latest date', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('span_days', 'date'))
    expect(result.tiles[0].value).toBe('4')
  })

  it('busiest_day: calendar day with the most rows', async () => {
    const result = await prepareStatsData(makeTable(), tileFor('busiest_day', 'date'))
    expect(result.tiles[0].value).toBe(expectedDay('2024-01-03T09:00:00.000Z'))
  })

  it('an aggregate requiring a column throws when column is omitted (surfaces as a data-prep error)', async () => {
    await expect(prepareStatsData(makeTable(), tileFor('distinct'))).rejects.toThrow()
  })

  it('degrades to a placeholder value, per tile, when the table is empty', async () => {
    const empty: Table = { id: 't1', head: { cells: ['date', 'duration', 'platform'] }, body: { rows: [] } }
    const result = await prepareStatsData(empty, tileFor('sum', 'duration'))
    expect(result.tiles[0].value).toBe('–')
  })

  it('degrades to a placeholder value when a numeric column has no valid values', async () => {
    const table: Table = {
      id: 't1',
      head: { cells: ['duration'] },
      body: { rows: [{ id: '0', cells: ['not-a-number'] }] }
    }
    const result = await prepareStatsData(table, tileFor('mean', 'duration'))
    expect(result.tiles[0].value).toBe('–')
  })

  it('computes every tile in a multi-tile block', async () => {
    const visualization: StatsVisualization = {
      title: {},
      type: 'stats',
      tiles: [
        { label: { en: 'total' }, aggregate: 'count' },
        { label: { en: 'platforms' }, aggregate: 'distinct', column: 'platform' }
      ]
    }
    const result = await prepareStatsData(makeTable(), visualization)
    expect(result.tiles.map((t) => t.value)).toEqual(['4', '2'])
    expect(result.tiles.map((t) => t.label)).toEqual([{ en: 'total' }, { en: 'platforms' }])
  })
})
