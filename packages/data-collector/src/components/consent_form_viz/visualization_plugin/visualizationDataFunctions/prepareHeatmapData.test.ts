import { prepareHeatmapData } from './prepareHeatmapData'
import { Table, HeatmapVisualization } from '../types'

function makeTable (rows: Array<[string, string?]>, columns: string[] = ['date', 'value']): Table {
  return {
    id: 't1',
    head: { cells: columns },
    body: { rows: rows.map(([date, value], i) => ({ id: String(i), cells: value === undefined ? [date] : [date, value] })) }
  }
}

describe('prepareHeatmapData empty table', () => {
  it('returns no grids for an empty table', async () => {
    const visualization: HeatmapVisualization = { title: {}, type: 'heatmap', mode: 'calendar', dateColumn: 'date' }
    const result = await prepareHeatmapData(makeTable([]), visualization)
    expect(result.grids).toEqual([])
    expect(result.max).toBe(0)
  })

  it('returns no grids when every date cell is unparseable', async () => {
    const visualization: HeatmapVisualization = { title: {}, type: 'heatmap', mode: 'weekday_hour', dateColumn: 'date' }
    const result = await prepareHeatmapData(makeTable([['not-a-date'], ['also-not-a-date']], ['date']), visualization)
    expect(result.grids).toEqual([])
  })
})

describe('prepareHeatmapData weekday_hour mode', () => {
  // Built from local wall-clock components, not a fixed UTC instant, so the
  // weekday/hour bucket this lands in is correct under any runner timezone
  // (mirrors prepareHeatmapData.ts's own local-time date handling).
  function localIso (y: number, monthIndex: number, day: number, hour: number, minute = 0): string {
    return new Date(y, monthIndex, day, hour, minute).toISOString()
  }

  function isoWeekdayOf (y: number, monthIndex: number, day: number, hour: number, minute = 0): number {
    return (new Date(y, monthIndex, day, hour, minute).getDay() + 6) % 7 // 0 = Monday .. 6 = Sunday
  }

  it('buckets rows into a 7x24 grid of row=weekday, col=hour counts', async () => {
    const visualization: HeatmapVisualization = { title: {}, type: 'heatmap', mode: 'weekday_hour', dateColumn: 'date' }
    const table = makeTable([
      [localIso(2024, 0, 1, 9)], // Monday, 9am local
      [localIso(2024, 0, 1, 9, 30)], // same weekday+hour bucket
      [localIso(2024, 0, 8, 15)] // next Monday, 3pm local
    ], ['date'])

    const result = await prepareHeatmapData(table, visualization)
    expect(result.mode).toBe('weekday_hour')
    expect(result.grids).toHaveLength(1)
    const grid = result.grids[0]
    expect(grid.rowLabels).toHaveLength(7)
    expect(grid.rowTooltipLabels).toHaveLength(7)
    expect(grid.values).toHaveLength(7)
    expect(grid.values[0]).toHaveLength(24)

    const mondayRow = isoWeekdayOf(2024, 0, 1, 9)
    expect(grid.values[mondayRow][9]).toBe(2)
    expect(grid.values[mondayRow][15]).toBe(1)
    expect(result.max).toBe(2)

    const total = grid.values.flat().reduce((a, b) => a + b, 0)
    expect(total).toBe(3)
  })

  it('supports a valueColumn with sum/mean aggregation', async () => {
    const visualization: HeatmapVisualization = {
      title: {}, type: 'heatmap', mode: 'weekday_hour', dateColumn: 'date', valueColumn: 'value', aggregate: 'sum'
    }
    const table = makeTable([
      [localIso(2024, 0, 1, 9), '10'],
      [localIso(2024, 0, 1, 9, 15), '5']
    ])
    const result = await prepareHeatmapData(table, visualization)
    const row = isoWeekdayOf(2024, 0, 1, 9)
    expect(result.grids[0].values[row][9]).toBe(15)
  })

  it('treats a non-numeric valueColumn cell as 0 instead of poisoning the sum with NaN', async () => {
    const visualization: HeatmapVisualization = {
      title: {}, type: 'heatmap', mode: 'weekday_hour', dateColumn: 'date', valueColumn: 'value', aggregate: 'sum'
    }
    const table = makeTable([
      [localIso(2024, 0, 1, 9), '10'],
      [localIso(2024, 0, 1, 9, 15), 'not-a-number']
    ])
    const result = await prepareHeatmapData(table, visualization)
    const row = isoWeekdayOf(2024, 0, 1, 9)
    expect(result.grids[0].values[row][9]).toBe(10)
  })

  it('excludes a blank valueColumn cell from a mean instead of counting it as a real zero', async () => {
    const visualization: HeatmapVisualization = {
      title: {}, type: 'heatmap', mode: 'weekday_hour', dateColumn: 'date', valueColumn: 'value', aggregate: 'mean'
    }
    const table = makeTable([
      [localIso(2024, 0, 1, 9), '10'],
      [localIso(2024, 0, 1, 9, 15), ''],
      [localIso(2024, 0, 1, 9, 30), '20']
    ])
    const result = await prepareHeatmapData(table, visualization)
    const row = isoWeekdayOf(2024, 0, 1, 9)
    // (10 + 20) / 2, not (10 + 0 + 20) / 3 -- Number('') is 0, not NaN.
    expect(result.grids[0].values[row][9]).toBe(15)
  })
})

describe('prepareHeatmapData calendar mode', () => {
  it('groups by year with rows=weekday, columns=week, and labels month boundaries', async () => {
    const visualization: HeatmapVisualization = { title: {}, type: 'heatmap', mode: 'calendar', dateColumn: 'date' }
    const table = makeTable([
      ['2024-01-01T12:00:00.000Z'],
      ['2024-01-01T12:30:00.000Z'], // same calendar day as above, in any reasonable timezone
      ['2024-02-14T12:00:00.000Z']
    ], ['date'])

    const result = await prepareHeatmapData(table, visualization)
    expect(result.mode).toBe('calendar')
    expect(result.grids).toHaveLength(1)
    const grid = result.grids[0]
    expect(grid.key).toBe('2024')
    expect(grid.rowLabels).toHaveLength(7)

    // find the cell for 2024-01-01 via cellDates and check its count
    let found = false
    for (let row = 0; row < grid.values.length; row++) {
      for (let col = 0; col < grid.values[row].length; col++) {
        if (grid.cellDates?.[row]?.[col] === '2024-01-01') {
          expect(grid.values[row][col]).toBe(2)
          found = true
        }
      }
    }
    expect(found).toBe(true)

    // a month boundary is recorded for January (col 0-ish) and February
    expect(grid.colGroups?.length).toBeGreaterThanOrEqual(2)
    expect(grid.colGroups?.[0].col).toBe(0)
  })

  it('produces one grid per year present in the data', async () => {
    const visualization: HeatmapVisualization = { title: {}, type: 'heatmap', mode: 'calendar', dateColumn: 'date' }
    const table = makeTable([
      ['2023-06-01T12:00:00.000Z'],
      ['2024-06-01T12:00:00.000Z']
    ], ['date'])

    const result = await prepareHeatmapData(table, visualization)
    expect(result.grids.map((g) => g.key)).toEqual(['2023', '2024'])
  })

  it('ignores rows with an unparseable date instead of throwing', async () => {
    const visualization: HeatmapVisualization = { title: {}, type: 'heatmap', mode: 'calendar', dateColumn: 'date' }
    const table = makeTable([
      ['2024-01-01T12:00:00.000Z'],
      ['not-a-date']
    ], ['date'])

    const result = await prepareHeatmapData(table, visualization)
    expect(result.grids).toHaveLength(1)
    const total = result.grids[0].values.flat().reduce((a, b) => a + b, 0)
    expect(total).toBe(1)
  })
})
