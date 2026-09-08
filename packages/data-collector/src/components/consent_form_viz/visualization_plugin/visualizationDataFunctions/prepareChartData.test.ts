import { prepareChartData } from './prepareChartData'
import { Table, ChartVisualization } from '../types'

function makeTable (rows: Array<[string, string]>): Table {
  return {
    id: 't1',
    head: { cells: ['group', 'val'] },
    body: {
      rows: rows.map(([group, val], i) => ({ id: String(i), cells: [group, val] }))
    }
  }
}

// Pins the fix for the no-constant-binary-expression lint findings at
// prepareChartData.ts:120 and :138: `Number(yValue) ?? 0` never falls back,
// because Number() never returns null/undefined (only NaN for unparsable
// input) -- so a non-numeric cell used to poison the running sum with NaN
// instead of being treated as 0.
describe('prepareChartData non-numeric value handling', () => {
  it('treats a non-numeric cell as 0 for a sum aggregation instead of poisoning the group with NaN', async () => {
    const table = makeTable([
      ['a', '10'],
      ['a', 'not-a-number'],
      ['b', '5']
    ])
    const visualization: ChartVisualization = {
      title: {},
      type: 'bar',
      group: { column: 'group' },
      values: [{ column: 'val', aggregate: 'sum' }]
    }

    const result = await prepareChartData(table, visualization)
    const groupA = result.data.find((d) => d.group === 'a')
    const groupB = result.data.find((d) => d.group === 'b')

    expect(groupA?.val).toBe(10)
    expect(groupB?.val).toBe(5)
  })

  it('treats a non-numeric cell as 0 in the pct aggregation denominator instead of poisoning every percentage with NaN', async () => {
    const table = makeTable([
      ['a', '10'],
      ['a', 'not-a-number'],
      ['b', '5']
    ])
    const visualization: ChartVisualization = {
      title: {},
      type: 'bar',
      group: { column: 'group' },
      values: [{ column: 'val', aggregate: 'pct' }]
    }

    const result = await prepareChartData(table, visualization)
    const groupA = result.data.find((d) => d.group === 'a')
    const groupB = result.data.find((d) => d.group === 'b')

    expect(Number.isFinite(groupA?.val)).toBe(true)
    expect(Number.isFinite(groupB?.val)).toBe(true)
    // createVisualizationData rounds values to 2 decimals.
    expect(groupA?.val).toBeCloseTo((100 * 10) / 15, 1)
    expect(groupB?.val).toBeCloseTo((100 * 5) / 15, 1)
  })
})

describe('prepareChartData top-N groups', () => {
  function makeTopTable (): Table {
    // counts: a=1, b=3, c=5, d=2 (first, and only, series is .COUNT)
    return makeTable([
      ['a', '1'],
      ['b', '1'], ['b', '1'], ['b', '1'],
      ['c', '1'], ['c', '1'], ['c', '1'], ['c', '1'], ['c', '1'],
      ['d', '1'], ['d', '1']
    ])
  }

  it('keeps the N groups with the largest first-series value, sorted descending, when top is smaller than the group count', async () => {
    const visualization: ChartVisualization = {
      title: {},
      type: 'bar',
      group: { column: 'group', top: 2 },
      values: [{ column: '.COUNT' }]
    }

    const result = await prepareChartData(makeTopTable(), visualization)
    expect(result.data.map((d) => d.group)).toEqual(['c', 'b'])
    expect(result.data.map((d) => d['.COUNT'])).toEqual([5, 3])
  })

  it('keeps every group, sorted descending, when top is larger than the group count', async () => {
    const visualization: ChartVisualization = {
      title: {},
      type: 'bar',
      group: { column: 'group', top: 100 },
      values: [{ column: '.COUNT' }]
    }

    const result = await prepareChartData(makeTopTable(), visualization)
    expect(result.data.map((d) => d.group)).toEqual(['c', 'b', 'd', 'a'])
  })

  it('leaves ordering unchanged (alphabetical/categorical) when top is absent', async () => {
    const visualization: ChartVisualization = {
      title: {},
      type: 'bar',
      group: { column: 'group' },
      values: [{ column: '.COUNT' }]
    }

    const result = await prepareChartData(makeTopTable(), visualization)
    expect(result.data.map((d) => d.group)).toEqual(['a', 'b', 'c', 'd'])
  })

  it('does not apply top when the group has a dateFormat (order is meaningful)', async () => {
    const table: Table = {
      id: 't1',
      head: { cells: ['date', 'val'] },
      body: {
        rows: [
          { id: '0', cells: ['2020-01-01T00:00:00.000Z', '1'] },
          { id: '1', cells: ['2021-01-01T00:00:00.000Z', '1'] },
          { id: '2', cells: ['2022-01-01T00:00:00.000Z', '1'] }
        ]
      }
    }
    const visualization: ChartVisualization = {
      title: {},
      type: 'bar',
      group: { column: 'date', dateFormat: 'year', top: 1 },
      values: [{ column: '.COUNT' }]
    }

    const result = await prepareChartData(table, visualization)
    // all three years kept, in chronological order, despite top: 1
    expect(result.data.map((d) => d.date)).toEqual(['2020', '2021', '2022'])
  })
})
