import { TableWithContext } from "./types"

// Inputs for the column sizing. Character counts are a rough proxy for
// rendered width, which is accurate enough to divide up a table.
export const WIDTH_SAMPLE_ROWS = 200 // representative, cheap on huge tables
export const MIN_CHARS = 3 // floor, so a column of one-character values stays clickable
export const COMFORT_CHARS = 12 // a column is never squeezed below this; the table scrolls instead
export const MAX_CHARS = 48 // past this a column stops asking for more of the spare room
// Deliberately wider than an average character at the largest table font size
// (md:text-base). Overestimating only costs space in the long columns, which
// have room to spare, while underestimating truncates the short ones.
export const CHAR_PX = 10
export const CELL_PADDING_PX = 24 // px-3 on both sides of a cell
export const CHECKBOX_COLUMN_PX = 32

function clamp (value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high)
}

/**
 * Divides `available` pixels over the columns, given the length in characters
 * of the longest value in each. Every column is served its comfortable width
 * before any column gets more than that, so a wide column never starves a
 * narrow one. Returns widths that may add up to more than `available`, in
 * which case the table is meant to scroll horizontally rather than squeeze.
 */
export function distributeColumnWidths (charCounts: number[], available: number): number[] {
  const width = (chars: number, cap: number): number => clamp(chars, MIN_CHARS, cap) * CHAR_PX + CELL_PADDING_PX
  const minimum = charCounts.map((chars) => width(chars, COMFORT_CHARS))
  const desired = charCounts.map((chars) => width(chars, MAX_CHARS))
  const total = (widths: number[]): number => widths.reduce((sum, w) => sum + w, 0)

  if (available <= total(minimum)) return minimum

  if (available < total(desired)) {
    // Between the two: move every column the same fraction of the way from
    // its minimum towards its desired width.
    const progress = (available - total(minimum)) / (total(desired) - total(minimum))
    return minimum.map((min, i) => min + progress * (desired[i] - min))
  }

  // Room to spare. Give it to the columns whose values are still cut off at
  // the desired width, or spread it evenly when nothing is being truncated.
  const unmet = charCounts.map((chars) => Math.max(chars - MAX_CHARS, 0))
  const totalUnmet = total(unmet)
  const spare = available - total(desired)
  return desired.map(
    (want, i) => want + spare * (totalUnmet > 0 ? unmet[i] / totalUnmet : 1 / desired.length)
  )
}

/**
 * Length of the longest value per column, from a sample of originalBody so
 * the layout does not jump while the participant searches, deletes rows or
 * pages (ADR-0031). Starts from the translated header's length.
 */
export function longestCellChars (table: TableWithContext, columnNames: string[]): number[] {
  const sample = table.originalBody.rows.slice(0, WIDTH_SAMPLE_ROWS)
  return columnNames.map((name, i) => {
    let longest = (table.headers?.[name] ?? name).length
    for (const row of sample) {
      const length = row.cells[i]?.length ?? 0
      if (length > longest) longest = length
    }
    return longest
  })
}
