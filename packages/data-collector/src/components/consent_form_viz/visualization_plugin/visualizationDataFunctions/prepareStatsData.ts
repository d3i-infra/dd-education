import { formatDate, getTableColumn } from './util'
import { DateFormat, StatsVisualizationData, StatsVisualization, StatTile, StatTileData, Table } from '../types'

// Rendered for a tile that has nothing to say (empty table, or no valid
// values for that tile's column) -- never thrown, so the other tiles in the
// same block still render.
const NO_VALUE = '–' // en dash

export async function prepareStatsData (table: Table, visualization: StatsVisualization): Promise<StatsVisualizationData> {
  const tiles: StatTileData[] = visualization.tiles.map((tile) => ({
    label: tile.label,
    value: table.body.rows.length === 0 ? NO_VALUE : computeTile(table, tile)
  }))

  return { type: 'stats', tiles }
}

function computeTile (table: Table, tile: StatTile): string {
  switch (tile.aggregate) {
    case 'count': return String(countRows(table, tile))
    case 'distinct': return String(distinctCount(table, tile))
    case 'min': return formatNumber(reduceNumeric(table, tile, (values) => Math.min(...values)))
    case 'max': return formatNumber(reduceNumeric(table, tile, (values) => Math.max(...values)))
    case 'sum': return formatNumber(reduceNumeric(table, tile, (values) => values.reduce((a, b) => a + b, 0)))
    case 'mean': return formatNumber(reduceNumeric(table, tile, (values) => values.reduce((a, b) => a + b, 0) / values.length))
    case 'first_date': return firstOrLastDate(table, tile, 'first')
    case 'last_date': return firstOrLastDate(table, tile, 'last')
    case 'span_days': return spanDays(table, tile)
    case 'busiest_day': return busiestDay(table, tile)
    default: throw new Error(`Unsupported stat aggregate: ${String(tile.aggregate)}`)
  }
}

function requireColumn (tile: StatTile): string {
  if (tile.column === undefined) throw new Error(`Stat tile aggregate '${tile.aggregate}' requires a column`)
  return tile.column
}

function countRows (table: Table, tile: StatTile): number {
  if (tile.column === undefined) return table.body.rows.length
  return getTableColumn(table, tile.column).filter((value) => value !== '').length
}

function distinctCount (table: Table, tile: StatTile): number {
  const column = requireColumn(tile)
  const values = getTableColumn(table, column).filter((value) => value !== '')
  return new Set(values).size
}

function numericValues (table: Table, tile: StatTile): number[] {
  const column = requireColumn(tile)
  return getTableColumn(table, column)
    // Number('') is 0, not NaN -- exclude blanks explicitly so a missing
    // value never masquerades as a real zero in min/max/mean.
    .filter((value) => value !== '')
    .map((value) => Number(value))
    .filter((value) => !Number.isNaN(value))
}

function reduceNumeric (table: Table, tile: StatTile, reduce: (values: number[]) => number): number | null {
  const values = numericValues(table, tile)
  if (values.length === 0) return null
  return reduce(values)
}

function formatNumber (value: number | null): string {
  if (value === null) return NO_VALUE
  return String(Math.round(value * 100) / 100)
}

function validDateTimes (table: Table, tile: StatTile): number[] {
  const column = requireColumn(tile)
  return getTableColumn(table, column)
    .map((value) => new Date(value).getTime())
    .filter((time) => !Number.isNaN(time))
}

function formatEpoch (time: number, dateFormat?: DateFormat): string {
  const [formatted] = formatDate([new Date(time).toISOString()], dateFormat ?? 'day')
  return formatted[0]
}

function firstOrLastDate (table: Table, tile: StatTile, which: 'first' | 'last'): string {
  const times = validDateTimes(table, tile)
  if (times.length === 0) return NO_VALUE
  const target = which === 'first' ? Math.min(...times) : Math.max(...times)
  return formatEpoch(target, tile.dateFormat)
}

function spanDays (table: Table, tile: StatTile): string {
  const times = validDateTimes(table, tile)
  if (times.length === 0) return NO_VALUE
  const spanMs = Math.max(...times) - Math.min(...times)
  return String(Math.round(spanMs / (1000 * 60 * 60 * 24)))
}

function busiestDay (table: Table, tile: StatTile): string {
  const column = requireColumn(tile)
  const rawValues = getTableColumn(table, column)
  const times = rawValues.map((value) => new Date(value).getTime())
  const [dayBuckets] = formatDate(rawValues, 'day')

  const counts: Record<string, number> = {}
  for (let i = 0; i < dayBuckets.length; i++) {
    if (Number.isNaN(times[i])) continue
    counts[dayBuckets[i]] = (counts[dayBuckets[i]] ?? 0) + 1
  }

  const entries = Object.entries(counts)
  if (entries.length === 0) return NO_VALUE
  entries.sort((a, b) => b[1] - a[1])
  const [busiestBucket] = entries[0]

  if (tile.dateFormat === undefined || tile.dateFormat === 'day') return busiestBucket

  // Reformat the winning day using the requested precision, off one of its
  // representative timestamps.
  const idx = dayBuckets.findIndex((bucket, i) => bucket === busiestBucket && !Number.isNaN(times[i]))
  if (idx < 0) return busiestBucket
  return formatEpoch(times[idx], tile.dateFormat)
}
