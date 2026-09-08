import { getTableColumn } from './util'
import { DEFAULT_THREAD_PAGE_SIZE, Label, Table, Thread, ThreadTurn, ThreadVisualization, ThreadVisualizationData } from '../types'

// A researcher-misconfigured export (or a very active participant) could in
// principle group into an unbounded number of threads; cap the list so a
// single figure can never balloon into tens of thousands of DOM buttons.
const MAX_THREADS = 5000

interface Group {
  title: Label
  rows: number[]
}

export async function prepareThreadData (table: Table, visualization: ThreadVisualization): Promise<ThreadVisualizationData> {
  const pageSize = {
    threads: visualization.pageSize?.threads ?? DEFAULT_THREAD_PAGE_SIZE.threads,
    turns: visualization.pageSize?.turns ?? DEFAULT_THREAD_PAGE_SIZE.turns,
  }
  const empty: ThreadVisualizationData = { type: 'thread', threads: [], truncated: false, pageSize, selfRole: visualization.selfRole }
  if (table.body.rows.length === 0) return empty

  const groups = groupRows(table, visualization)
  const truncated = groups.length > MAX_THREADS
  const kept = truncated ? groups.slice(0, MAX_THREADS) : groups

  const times = visualization.timeColumn !== undefined ? getTableColumn(table, visualization.timeColumn) : null
  const roles = getTableColumn(table, visualization.roleColumn)
  const texts = getTableColumn(table, visualization.textColumn)
  const badges = visualization.badgeColumn !== undefined ? getTableColumn(table, visualization.badgeColumn) : null

  const threads: Thread[] = kept.map(({ title, rows }, index) => {
    const orderedRows = times !== null ? sortByTime(rows, times) : rows
    const turns: ThreadTurn[] = orderedRows.map((row) => buildTurn(row, roles, texts, times, badges))
    const [firstTime, lastTime] = times !== null ? timeSpan(rows, times) : [undefined, undefined]

    return {
      id: String(index),
      title,
      count: rows.length,
      firstTime,
      lastTime,
      turns,
    }
  })

  return { type: 'thread', threads, truncated, pageSize, selfRole: visualization.selfRole }
}

// Groups row indices by groupColumn's cell value, preserving the order each
// group first appears in the table. In single-thread mode (no groupColumn --
// a flat chat export, see types.ts) every row belongs to the one group.
function groupRows (table: Table, visualization: ThreadVisualization): Group[] {
  if (visualization.groupColumn === undefined) {
    const rows = table.body.rows.map((_, i) => i)
    return [{ title: visualization.singleThreadTitle ?? '', rows }]
  }

  const keys = getTableColumn(table, visualization.groupColumn)
  const order: string[] = []
  const byKey: Record<string, Group> = {}

  for (let i = 0; i < keys.length; i++) {
    const key = keys[i]
    if (byKey[key] === undefined) {
      byKey[key] = { title: key, rows: [] }
      order.push(key)
    }
    byKey[key].rows.push(i)
  }

  return order.map((key) => byKey[key])
}

function buildTurn (row: number, roles: string[], texts: string[], times: string[] | null, badges: string[] | null): ThreadTurn {
  const turn: ThreadTurn = { role: roles[row], text: texts[row] }
  if (times !== null && !Number.isNaN(new Date(times[row]).getTime())) turn.time = times[row]
  if (badges !== null && badges[row] !== '') turn.badge = badges[row]
  return turn
}

// Ascending by parsed time; a row whose cell doesn't parse sorts after every
// parseable row, keeping its original relative order among other unparseable
// rows (Array.prototype.sort is stable, ES2019+).
function sortByTime (rows: number[], times: string[]): number[] {
  return [...rows].sort((a, b) => {
    const ta = new Date(times[a]).getTime()
    const tb = new Date(times[b]).getTime()
    const aValid = !Number.isNaN(ta)
    const bValid = !Number.isNaN(tb)
    if (aValid && bValid) return ta - tb
    if (aValid !== bValid) return aValid ? -1 : 1
    return 0
  })
}

function timeSpan (rows: number[], times: string[]): [string | undefined, string | undefined] {
  const parsed = rows.map((row) => new Date(times[row]).getTime()).filter((t) => !Number.isNaN(t))
  if (parsed.length === 0) return [undefined, undefined]
  return [new Date(Math.min(...parsed)).toISOString(), new Date(Math.max(...parsed)).toISOString()]
}
