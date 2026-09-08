/** @jest-environment jsdom */
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import ThreadView from "./thread_view"
import { ThreadVisualizationData } from "../types"

// React 19 gates `act()` warnings behind this global instead of
// react-dom/test-utils — see issue_form.test.tsx for the same setup.
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function makeThreads(n: number, turnsPerThread = 1): ThreadVisualizationData["threads"] {
  return Array.from({ length: n }, (_, i) => ({
    id: String(i),
    title: `Conversation ${i}`,
    count: turnsPerThread,
    firstTime: "2024-01-01T00:00:00.000Z",
    lastTime: "2024-01-01T00:00:00.000Z",
    turns: Array.from({ length: turnsPerThread }, (_, t) => ({
      role: t % 2 === 0 ? "user" : "assistant",
      text: `turn ${t} of conversation ${i}`,
    })),
  }))
}

function baseData(overrides: Partial<ThreadVisualizationData> = {}): ThreadVisualizationData {
  return {
    type: "thread",
    threads: makeThreads(3),
    truncated: false,
    pageSize: { threads: 20, turns: 50 },
    selfRole: "user",
    ...overrides,
  }
}

function renderThreadView(container: HTMLDivElement, data: ThreadVisualizationData): Root {
  const root = createRoot(container)
  act(() => {
    root.render(<ThreadView visualizationData={data} locale="en" />)
  })
  return root
}

function threadButtons(container: HTMLDivElement): HTMLButtonElement[] {
  return Array.from(container.querySelectorAll<HTMLButtonElement>("button[data-thread-id]"))
}

function findButtonByText(root: HTMLElement, text: string): HTMLButtonElement {
  const button = Array.from(root.querySelectorAll<HTMLButtonElement>("button")).find(
    (el) => el.textContent?.trim() === text
  )
  if (button === undefined) throw new Error(`no button found with text "${text}"`)
  return button
}

// Both panes render their own Previous/Next controls, so a turn-paging
// assertion must scope its query to the transcript pane specifically.
function transcriptPane(container: HTMLDivElement): HTMLElement {
  const pane = container.querySelector<HTMLElement>('[data-pane="transcript"]')
  if (pane === null) throw new Error("transcript pane not found")
  return pane
}

function listPane(container: HTMLDivElement): HTMLElement {
  const pane = container.querySelector<HTMLElement>('[data-pane="list"]')
  if (pane === null) throw new Error("list pane not found")
  return pane
}

describe("ThreadView", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement("div")
    document.body.appendChild(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  test("renders no DOM for an empty threads list (figure.tsx renders the fallback instead)", () => {
    root = renderThreadView(container, baseData({ threads: [] }))
    expect(container.innerHTML).toBe("")
  })

  test("renders the thread list, one button per thread, page 1", () => {
    root = renderThreadView(container, baseData())
    const buttons = threadButtons(container)
    expect(buttons).toHaveLength(3)
    expect(buttons.map((b) => b.dataset.threadId)).toEqual(["0", "1", "2"])
    expect(buttons[0].textContent).toContain("Conversation 0")
  })

  test("shows a select prompt and no turns before any thread is selected", () => {
    root = renderThreadView(container, baseData())
    expect(container.textContent).toContain("Select a conversation")
  })

  test("selecting a thread shows its turns", () => {
    root = renderThreadView(container, baseData({ threads: makeThreads(2, 3) }))
    const buttons = threadButtons(container)
    act(() => {
      buttons[0].dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    expect(container.textContent).toContain("turn 0 of conversation 0")
    expect(container.textContent).toContain("turn 2 of conversation 0")
    expect(container.textContent).not.toContain("conversation 1")
  })

  test("paging turns: Next reveals the next page, Previous returns to the first", () => {
    root = renderThreadView(container, baseData({ threads: makeThreads(1, 5), pageSize: { threads: 20, turns: 2 } }))
    act(() => {
      threadButtons(container)[0].dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    expect(container.textContent).toContain("turn 0 of conversation 0")
    expect(container.textContent).toContain("turn 1 of conversation 0")
    expect(container.textContent).not.toContain("turn 2 of conversation 0")

    act(() => {
      findButtonByText(transcriptPane(container), "Next").dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    expect(container.textContent).toContain("turn 2 of conversation 0")
    expect(container.textContent).toContain("turn 3 of conversation 0")
    expect(container.textContent).not.toContain("turn 0 of conversation 0")

    act(() => {
      findButtonByText(transcriptPane(container), "Previous").dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    expect(container.textContent).toContain("turn 0 of conversation 0")
  })

  test("paging threads: Next reveals the next page of the list", () => {
    root = renderThreadView(container, baseData({ threads: makeThreads(3), pageSize: { threads: 1, turns: 50 } }))
    expect(threadButtons(container).map((b) => b.dataset.threadId)).toEqual(["0"])

    act(() => {
      findButtonByText(listPane(container), "Next").dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    expect(threadButtons(container).map((b) => b.dataset.threadId)).toEqual(["1"])
  })

  test("the '1-N of total' label reflects the current threads page", () => {
    root = renderThreadView(container, baseData({ threads: makeThreads(3), pageSize: { threads: 2, turns: 50 } }))
    expect(container.textContent).toContain("1–2 of 3")
  })

  test("search filters the thread list by title", () => {
    root = renderThreadView(container, baseData())
    const search = container.querySelector<HTMLInputElement>('input[type="search"]')
    if (search === null) throw new Error("search input not found")

    act(() => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set
      setter?.call(search, "Conversation 1")
      search.dispatchEvent(new Event("input", { bubbles: true }))
    })

    expect(threadButtons(container).map((b) => b.dataset.threadId)).toEqual(["1"])
  })

  test("search also filters by message text, not just title", () => {
    const threads = makeThreads(2)
    threads[0].turns = [{ role: "user", text: "a rare phrase" }]
    threads[1].turns = [{ role: "user", text: "nothing special" }]
    root = renderThreadView(container, baseData({ threads }))

    const search = container.querySelector<HTMLInputElement>('input[type="search"]')
    if (search === null) throw new Error("search input not found")
    act(() => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set
      setter?.call(search, "rare phrase")
      search.dispatchEvent(new Event("input", { bubbles: true }))
    })

    expect(threadButtons(container).map((b) => b.dataset.threadId)).toEqual(["0"])
  })

  test("selfRole rows align right, other roles align left", () => {
    const threads = makeThreads(1, 2) // turn 0 role 'user' (selfRole), turn 1 role 'assistant'
    root = renderThreadView(container, baseData({ threads, selfRole: "user" }))
    act(() => {
      threadButtons(container)[0].dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    const bubbleRows = Array.from(container.querySelectorAll<HTMLElement>(".flex.justify-end, .flex.justify-start"))
    expect(bubbleRows).toHaveLength(2)
    expect(bubbleRows[0].className).toContain("justify-end")
    expect(bubbleRows[1].className).toContain("justify-start")
  })
})
