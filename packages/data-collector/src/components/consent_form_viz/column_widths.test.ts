import { distributeColumnWidths, longestCellChars, CHAR_PX, CELL_PADDING_PX, COMFORT_CHARS, MAX_CHARS, MIN_CHARS } from "./column_widths"

const w = (chars: number): number => chars * CHAR_PX + CELL_PADDING_PX

test("below the comfortable total every column gets its comfortable minimum and the table overflows", () => {
  const out = distributeColumnWidths([50, 50, 50], 100)
  expect(out).toEqual([w(COMFORT_CHARS), w(COMFORT_CHARS), w(COMFORT_CHARS)])
})

test("a one-character column never drops under MIN_CHARS", () => {
  expect(distributeColumnWidths([1], 10)[0]).toBe(w(MIN_CHARS))
})

test("between minimum and desired, columns move the same fraction of the way", () => {
  const counts = [20, 40]
  const min = counts.map((c) => w(Math.min(c, COMFORT_CHARS)))
  const desired = counts.map((c) => w(Math.min(c, MAX_CHARS)))
  const half = (min[0] + min[1] + desired[0] + desired[1]) / 2
  const out = distributeColumnWidths(counts, half)
  expect(out[0]).toBeCloseTo(min[0] + 0.5 * (desired[0] - min[0]))
  expect(out[1]).toBeCloseTo(min[1] + 0.5 * (desired[1] - min[1]))
})

test("spare room goes to the columns still truncating, or evenly when none are", () => {
  const cut = distributeColumnWidths([100, 5], 2000)
  expect(cut[0]).toBeGreaterThan(cut[1] * 5)
  const even = distributeColumnWidths([5, 5], 1000)
  expect(even[0]).toBeCloseTo(even[1])
  expect(even[0] + even[1]).toBeCloseTo(1000)
})

test("longestCellChars samples originalBody and counts the header too", () => {
  const table: any = {
    headers: { a: "A long translated header" },
    originalBody: { rows: [{ id: "1", cells: ["x", "yyyyyy"] }, { id: "2", cells: ["zzz", "y"] }] },
  }
  expect(longestCellChars(table, ["a", "b"])).toEqual(["A long translated header".length, 6])
})
