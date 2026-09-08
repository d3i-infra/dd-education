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
  it('buckets rows into a 7x24 grid of row=weekday, col=hour counts', async () => {
    const visualization: HeatmapVisualization = { title: {}, type: 'heatmap', mode: 'weekday_hour', dateColumn: 'date' }
    const table = makeTable([
      ['2024-01-01T09:00:00.000Z'], // Monday, 9am UTC
      ['2024-01-01T09:30:00.000Z'], // same weekday+hour bucket
      ['2024-01-08T15:00:00.000Z'] // next Monday, 3pm UTC
    ], ['date'])

    const result = await prepareHeatmapData(table, visualization)
    expect(result.mode).toBe('weekday_hour')
    expect(result.grids).toHaveLength(1)
    const grid = result.grids[0]
    expect(grid.rowLabels).toHaveLength(7)
    expect(grid.values).toHaveLength(7)
    expect(grid.values[0]).toHaveLength(24)

    const mondayRow = 0 // Monday is row 0 (Monday-first week)
    const nineAmDate = new Date('2024-01-01T09:00:00.000Z')
    const threePmDate = new Date('2024-01-08T15:00:00.000Z')
    expect(grid.values[mondayRow][nineAmDate.getHours()]).toBe(2)
    expect(grid.values[mondayRow][threePmDate.getHours()]).toBe(1)
    expect(result.max).toBe(2)

    const total = grid.values.flat().reduce((a, b) => a + b, 0)
    expect(total).toBe(3)
  })

  it('supports a valueColumn with sum/mean aggregation', async () => {
    const visualization: HeatmapVisualization = {
      title: {}, type: 'heatmap', mode: 'weekday_hour', dateColumn: 'date', valueColumn: 'value', aggregate: 'sum'
    }
    const table = makeTable([
      ['2024-01-01T09:00:00.000Z', '10'],
      ['2024-01-01T09:15:00.000Z', '5']
    ])
    const result = await prepareHeatmapData(table, visualization)
    const date = new Date('2024-01-01T09:00:00.000Z')
    expect(result.grids[0].values[0][date.getHours()]).toBe(15)
  })

  it('treats a non-numeric valueColumn cell as 0 instead of poisoning the sum with NaN', async () => {
    const visualization: HeatmapVisualization = {
      title: {}, type: 'heatmap', mode: 'weekday_hour', dateColumn: 'date', valueColumn: 'value', aggregate: 'sum'
    }
    const table = makeTable([
      ['2024-01-01T09:00:00.000Z', '10'],
      ['2024-01-01T09:15:00.000Z', 'not-a-number']
    ])
    const result = await prepareHeatmapData(table, visualization)
    const date = new Date('2024-01-01T09:00:00.000Z')
    expect(result.grids[0].values[0][date.getHours()]).toBe(10)
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
