/** @jest-environment jsdom */
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"

import { Table } from "./table"
import { TableWithContext } from "./types"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

// jsdom always reports scrollWidth/clientWidth as 0, so a cell would never
// register as overflowing. Force a truncated layout for every cell's text
// div so the tap-to-expand path is reachable in these tests.
function stubOverflowingText(): void {
  Object.defineProperty(HTMLElement.prototype, "scrollWidth", { configurable: true, get: () => 500 })
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, get: () => 50 })
}

function stubCoarsePointer(matches: boolean): void {
  ;(window as unknown as { matchMedia: (query: string) => MediaQueryList }).matchMedia = jest
    .fn()
    .mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }))
}

const longText = "a very long cell value that will not fit in a narrow column and gets truncated"

function makeTable(): TableWithContext {
  const row = { id: "1", cells: [longText] }
  return {
    __type__: "PropsUITable",
    id: "t1",
    head: { cells: ["col"] },
    body: { rows: [row] },
    originalBody: { rows: [row] },
    title: "Test table",
    description: "",
    deletedRowCount: 0,
    annotations: [],
    deletedRows: [],
    folded: false,
    deleteOption: false,
  }
}

describe("Table cell tap-to-expand", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    stubOverflowingText()
    container = document.createElement("div")
    document.body.appendChild(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    jest.restoreAllMocks()
  })

  function textDiv(): HTMLDivElement {
    const el = container.querySelector<HTMLDivElement>("td div.relative > div")
    if (el === null) throw new Error("cell text div not found")
    return el
  }

  test("on a coarse pointer, clicking a truncated cell expands it to the full value", () => {
    stubCoarsePointer(true)
    root = createRoot(container)
    act(() => {
      root.render(
        <Table table={makeTable()} show unfilteredRows={1} locale="en" search="" />
      )
    })

    const before = textDiv()
    expect(before.className).toContain("whitespace-nowrap")

    const cellWrapper = before.parentElement
    if (cellWrapper === null) throw new Error("cell wrapper not found")
    act(() => {
      cellWrapper.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    const after = textDiv()
    expect(after.className).not.toContain("whitespace-nowrap")
    expect(after.className).toContain("whitespace-normal")
    expect(after.className).toContain("break-words")
    expect(after.textContent).toBe(longText)
  })

  test("on a coarse pointer, an expanded cell collapses again on the next tap", () => {
    stubCoarsePointer(true)
    root = createRoot(container)
    act(() => {
      root.render(
        <Table table={makeTable()} show unfilteredRows={1} locale="en" search="" />
      )
    })
    const cellWrapper = textDiv().parentElement
    if (cellWrapper === null) throw new Error("cell wrapper not found")
    act(() => { cellWrapper.dispatchEvent(new MouseEvent("click", { bubbles: true })) })
    expect(textDiv().className).toContain("whitespace-normal")
    // Once expanded the text wraps, so the overflow check would read false;
    // the collapse must not depend on it (Task 6 review finding).
    Object.defineProperty(HTMLElement.prototype, "scrollWidth", { configurable: true, get: () => 50 })
    act(() => { cellWrapper.dispatchEvent(new MouseEvent("click", { bubbles: true })) })
    expect(textDiv().className).toContain("whitespace-nowrap")
    expect(textDiv().className).not.toContain("whitespace-normal")
  })

  test("on a fine pointer, clicking a truncated cell does not expand it", () => {
    stubCoarsePointer(false)
    root = createRoot(container)
    act(() => {
      root.render(
        <Table table={makeTable()} show unfilteredRows={1} locale="en" search="" />
      )
    })

    const before = textDiv()
    const cellWrapper = before.parentElement
    if (cellWrapper === null) throw new Error("cell wrapper not found")
    act(() => {
      cellWrapper.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    const after = textDiv()
    expect(after.className).toContain("whitespace-nowrap")
    expect(after.className).not.toContain("whitespace-normal")
  })
})
