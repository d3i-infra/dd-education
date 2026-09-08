import { formatDate, getTableColumn } from './util'
import { HeatmapAggregate, HeatmapGrid, HeatmapVisualizationData, HeatmapVisualization, Table } from '../types'

// A known Monday-first week (matches formatDate's own "weekday_cycle" domain)
// used once to derive locale-correct weekday initials via util.ts, instead of
// hardcoding English day names. Noon UTC keeps every offset well clear of a
// local-day boundary.
const WEEKDAY_CYCLE_ISO = [
  '2023-11-06T12:00:00.000Z', // Monday
  '2023-11-07T12:00:00.000Z',
  '2023-11-08T12:00:00.000Z',
  '2023-11-09T12:00:00.000Z',
  '2023-11-10T12:00:00.000Z',
  '2023-11-11T12:00:00.000Z',
  '2023-11-12T12:00:00.000Z' // Sunday
]

const HOUR_TICK_INTERVAL = 3

interface Sample {
  time: number
  value: number
}

interface CellAccumulator {
  n: number
  sum: number
}

export async function prepareHeatmapData (table: Table, visualization: HeatmapVisualization): Promise<HeatmapVisualizationData> {
  const empty: HeatmapVisualizationData = { type: 'heatmap', mode: visualization.mode, max: 0, grids: [] }
  if (table.body.rows.length === 0) return empty

  const samples = collectSamples(table, visualization)
  if (samples.length === 0) return empty

  const aggregate = visualization.aggregate ?? 'count'
  if (visualization.mode === 'weekday_hour') return prepareWeekdayHour(samples, aggregate)
  return prepareCalendar(samples, aggregate)
}

function collectSamples (table: Table, visualization: HeatmapVisualization): Sample[] {
  const dates = getTableColumn(table, visualization.dateColumn)
  const values = visualization.valueColumn !== undefined ? getTableColumn(table, visualization.valueColumn) : null

  const samples: Sample[] = []
  for (let i = 0; i < dates.length; i++) {
    const time = new Date(dates[i]).getTime()
    if (Number.isNaN(time)) continue

    let value = 1
    if (values !== null) {
      const numeric = Number(values[i])
      value = Number.isNaN(numeric) ? 0 : numeric
    }
    samples.push({ time, value })
  }
  return samples
}

function accumulate (acc: Record<string, CellAccumulator>, key: string, value: number): void {
  if (acc[key] === undefined) acc[key] = { n: 0, sum: 0 }
  acc[key].n += 1
  acc[key].sum += value
}

function resolveAggregate (acc: CellAccumulator | undefined, aggregate: HeatmapAggregate): number {
  if (acc === undefined) return 0
  if (aggregate === 'sum') return acc.sum
  if (aggregate === 'mean') return acc.n === 0 ? 0 : acc.sum / acc.n
  return acc.n // count
}

// 0 = Monday .. 6 = Sunday, matching WEEKDAY_CYCLE_ISO / formatDate's weekday_cycle domain.
function isoWeekday (date: Date): number {
  return (date.getDay() + 6) % 7
}

function weekdayInitials (): string[] {
  const [names] = formatDate(WEEKDAY_CYCLE_ISO, 'weekday_cycle')
  return names.map((name) => name.charAt(0).toUpperCase())
}

function isLeapYear (year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0
}

function dayKey (date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function prepareWeekdayHour (samples: Sample[], aggregate: HeatmapAggregate): HeatmapVisualizationData {
  const acc: Record<string, CellAccumulator> = {}
  for (const { time, value } of samples) {
    const date = new Date(time)
    accumulate(acc, `${isoWeekday(date)}:${date.getHours()}`, value)
  }

  let max = 0
  const values: number[][] = []
  for (let row = 0; row < 7; row++) {
    const rowValues: number[] = []
    for (let col = 0; col < 24; col++) {
      const v = resolveAggregate(acc[`${row}:${col}`], aggregate)
      rowValues.push(v)
      if (v > max) max = v
    }
    values.push(rowValues)
  }

  const colLabels = Array.from({ length: 24 }, (_, hour) => (hour % HOUR_TICK_INTERVAL === 0 ? String(hour) : ''))

  const grid: HeatmapGrid = {
    key: '',
    rowLabels: weekdayInitials(),
    colLabels,
    values
  }

  return { type: 'heatmap', mode: 'weekday_hour', max, grids: [grid] }
}

function prepareCalendar (samples: Sample[], aggregate: HeatmapAggregate): HeatmapVisualizationData {
  const acc: Record<string, CellAccumulator> = {}
  for (const { time, value } of samples) accumulate(acc, dayKey(new Date(time)), value)

  const years = Array.from(new Set(samples.map((s) => new Date(s.time).getFullYear()))).sort((a, b) => a - b)
  const rowLabels = weekdayInitials()

  let max = 0
  const grids: HeatmapGrid[] = years.map((year) => {
    const jan1 = new Date(year, 0, 1)
    const startWeekday = isoWeekday(jan1)
    const totalDays = isLeapYear(year) ? 366 : 365
    const weeks = Math.ceil((startWeekday + totalDays) / 7)

    const values: number[][] = Array.from({ length: 7 }, () => Array(weeks).fill(0))
    const cellDates: string[][] = Array.from({ length: 7 }, () => Array(weeks).fill(''))
    const monthBoundaries: Array<{ col: number, iso: string }> = []
    let lastMonth = -1

    for (let d = 0; d < totalDays; d++) {
      const date = new Date(year, 0, 1 + d)
      const row = isoWeekday(date)
      const col = Math.floor((startWeekday + d) / 7)
      const key = dayKey(date)

      const v = resolveAggregate(acc[key], aggregate)
      values[row][col] = v
      cellDates[row][col] = key
      if (v > max) max = v

      const month = date.getMonth()
      if (month !== lastMonth) {
        monthBoundaries.push({ col, iso: date.toISOString() })
        lastMonth = month
      }
    }

    // One batched formatDate call per year (not per month boundary) so this
    // stays a single Intl.DateTimeFormat construction, per ADR-0035.
    const [monthFormatted] = formatDate(monthBoundaries.map((b) => b.iso), 'month')
    const colGroups = monthBoundaries.map((boundary, i) => ({
      col: boundary.col,
      // formatDate's "month" format is "<year>-<short month>"; drop the year, already shown once per grid.
      label: monthFormatted[i].slice(monthFormatted[i].indexOf('-') + 1)
    }))

    return {
      key: String(year),
      rowLabels,
      colLabels: Array<string>(weeks).fill(''),
      values,
      cellDates,
      colGroups
    }
  })

  return { type: 'heatmap', mode: 'calendar', max, grids }
}
