/** @jest-environment jsdom */
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"

// Only visualization_plugin/figure.tsx (via useVisualizationData.tsx)
// constructs a Web Worker with `new Worker(new URL(..., import.meta.url))` —
// syntax Jest's CJS-hybrid ts-jest transform cannot parse. Stubbing just that
// leaf lets the real TableContainer (title, search, table, review-mode
// layout) render for these tests instead of being replaced wholesale.
jest.mock("./visualization_plugin/figure", () => ({
  Figure: () => null,
}))

import { ConsentFormViz } from "./consent_form_viz"
import { PropsUIPromptConsentFormViz, PropsUIPromptConsentFormTableViz } from "./types"
import { ReactFactoryContext } from "@eyra/feldspar"

// React 19 gates `act()` warnings behind this global instead of
// react-dom/test-utils — see issue_form.test.tsx for the same setup.
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

type Props = PropsUIPromptConsentFormViz & ReactFactoryContext

const table: PropsUIPromptConsentFormTableViz = {
  __type__: "PropsUIPromptConsentFormTableViz",
  id: "test_table",
  title: "Test table",
  description: "",
  data_frame: JSON.stringify({ col: { "0": "a", "1": "b" } }),
  visualizations: undefined,
  folded: false,
  delete_option: true,
}

function baseProps(resolve: (payload: any) => void): Props {
  return {
    __type__: "PropsUIPromptConsentFormViz",
    description: "Review your data",
    tables: [table],
    locale: "en",
    resolve,
  }
}

function renderConsentFormViz(container: HTMLDivElement, props: Props): Root {
  const root = createRoot(container)
  act(() => {
    root.render(<ConsentFormViz {...props} />)
  })
  return root
}

function findButtonByText(container: HTMLDivElement, text: string): HTMLElement | null {
  const candidates = Array.from(container.querySelectorAll<HTMLElement>('[role="button"]'))
  return candidates.find((el) => el.textContent?.trim() === text) ?? null
}

// feldspar's button elements nest an `onClick` div a level or two below the
// outer `role="button"` wrapper (see PrimaryButton/LabelButton in
// button.tsx). A click only bubbles up through actual DOM ancestors, so it
// must be dispatched on the innermost leaf carrying the label text, not the
// outer wrapper `findButtonByText` returns for existence checks.
function clickButtonByText(container: HTMLDivElement, text: string): void {
  const leaves = Array.from(container.querySelectorAll<HTMLElement>("*")).filter(
    (el) => el.children.length === 0 && el.textContent?.trim() === text
  )
  const leaf = leaves[0]
  if (leaf === undefined) throw new Error(`no clickable element found for "${text}"`)
  act(() => {
    leaf.dispatchEvent(new MouseEvent("click", { bubbles: true }))
  })
}

describe("ConsentFormViz", () => {
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

  describe("reviewOnly: true (education mode)", () => {
    test("Continue resolves PayloadTrue without serializing", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, {
        ...baseProps(resolve),
        reviewOnly: true,
        donateButton: "Continue",
      })

      expect(findButtonByText(container, "Continue")).not.toBeNull()

      clickButtonByText(container, "Continue")

      expect(resolve).toHaveBeenCalledWith({ __type__: "PayloadTrue", value: true })
    })

    test("shows Report issues and no No/cancel button", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, {
        ...baseProps(resolve),
        reviewOnly: true,
        donateButton: "Continue",
      })

      expect(findButtonByText(container, "Report issues")).not.toBeNull()
      expect(findButtonByText(container, "No")).toBeNull()
    })
  })

  describe("reviewOnly absent (study mode)", () => {
    test("renders DonateButtons donate + cancel pair", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, baseProps(resolve))

      const donateButton = findButtonByText(container, "Yes, share for research")
      const cancelButton = findButtonByText(container, "No")
      expect(donateButton).not.toBeNull()
      expect(cancelButton).not.toBeNull()
    })

    test("cancel resolves PayloadFalse", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, baseProps(resolve))

      clickButtonByText(container, "No")

      expect(resolve).toHaveBeenCalledWith({ __type__: "PayloadFalse", value: false })
    })

    test("no Report issues button", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, baseProps(resolve))

      expect(findButtonByText(container, "Report issues")).toBeNull()
    })

    // Locks down the exact markup study mode produced before the review-ui
    // layout work (Task 19) — the review-only branch is a separate tree
    // entirely, so this DOM must never move as review mode evolves.
    test("layout DOM is unchanged by the review-layout work", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, baseProps(resolve))

      expect(container.innerHTML).toMatchSnapshot()
    })
  })

  // Task 19 (review-ui): the reviewOnly branch replaces the flat stack of
  // TableContainers with a chip strip + figures-first cards. These tables are
  // built directly (not through `table` above) so each has a distinct,
  // controllable row count.
  describe("reviewOnly: true — review layout", () => {
    function tableWithRows(id: string, title: string, rowCount: number): PropsUIPromptConsentFormTableViz {
      const column: Record<string, string> = {}
      for (let i = 0; i < rowCount; i++) column[String(i)] = `row-${i}`
      return {
        __type__: "PropsUIPromptConsentFormTableViz",
        id,
        title,
        description: "",
        data_frame: JSON.stringify({ col: column }),
        visualizations: undefined,
        folded: false,
        delete_option: true,
      }
    }

    function tableWithVisualizations(id: string, title: string, visualizations: any[]): PropsUIPromptConsentFormTableViz {
      return {
        ...tableWithRows(id, title, 2),
        visualizations,
      }
    }

    function multiTableProps(resolve: (payload: any) => void): Props {
      return {
        __type__: "PropsUIPromptConsentFormViz",
        description: "Review your data",
        tables: [
          tableWithRows("a", "Alpha table", 2),
          tableWithRows("b", "Beta table", 0),
          tableWithRows("c", "Gamma table", 3),
        ],
        locale: "en",
        resolve,
        reviewOnly: true,
        donateButton: "Continue",
      }
    }

    // Task 21 (hybrid review layout) fixtures: a table built with an
    // arbitrary set of visualizations (or none), and the two figure shapes
    // the featured-table rule cares about. `threadViz` needs `groupColumn`/
    // `roleColumn`/`textColumn` naming real columns of `tableWithRows`'
    // single "col" column (see figure.test.tsx for a valid thread shape).
    function makeTable(id: string, opts: { visualizations?: any[] } = {}): PropsUIPromptConsentFormTableViz {
      const visualizations = opts.visualizations ?? []
      return visualizations.length > 0
        ? tableWithVisualizations(id, id, visualizations)
        : tableWithRows(id, id, 2)
    }

    function threadViz(): any {
      return { type: "thread", title: { en: "Conversations" }, groupColumn: "col", roleColumn: "col", textColumn: "col" }
    }

    function bar(): any {
      return { type: "bar", title: { en: "A bar chart" }, group: { column: "col" }, values: [{ column: ".COUNT" }] }
    }

    // Regression: figure.tsx's chart/heatmap wrappers carry `relative z-50`
    // (upstream, not to be changed here), which painted over the chip strip
    // while scrolling unless the strip sits above them and stays opaque.
    test("the sticky chip strip stays above figures and opaque while scrolling", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, multiTableProps(resolve))

      const nav = container.querySelector("nav")
      if (nav === null) throw new Error("chip strip nav not found")

      const classes = nav.className.split(/\s+/)
      expect(classes).toContain("sticky")
      expect(classes).toContain("top-0")
      expect(classes).toContain("z-[60]")
      expect(classes).toContain("bg-white")
    })

    test("renders one chip per table with its row count", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, multiTableProps(resolve))

      const chips = Array.from(container.querySelectorAll<HTMLElement>("[data-chip-id]"))
      expect(chips).toHaveLength(3)

      const byId = (id: string): HTMLElement | undefined => chips.find((c) => c.dataset.chipId === id)
      expect(byId("a")?.textContent).toContain("Alpha table")
      expect(byId("a")?.textContent).toContain("2")
      expect(byId("b")?.textContent).toContain("Beta table")
      expect(byId("b")?.textContent).toContain("0")
      expect(byId("c")?.textContent).toContain("Gamma table")
      expect(byId("c")?.textContent).toContain("3")
    })

    // A thread figure's two-pane list+transcript layout needs the same full
    // width the stats/heatmap figures already get, or the transcript pane
    // has nowhere to grow (Danielle, live run).
    test("a thread figure's wrapper spans both columns of the review grid, like stats and heatmap", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, {
        ...multiTableProps(resolve),
        tables: [
          tableWithVisualizations("a", "Alpha table", [
            { type: "thread", title: { en: "Conversations" }, groupColumn: "col", roleColumn: "col", textColumn: "col" },
            { type: "bar", title: { en: "A bar chart" }, group: { column: "col" }, values: [{ column: ".COUNT" }] },
          ]),
        ],
      })

      // A thread figure makes this table featured (task 21), so it's off the
      // overview and only mounted on its own page — open it via its page chip.
      act(() => {
        container.querySelector('[data-page-chip="a"]')!.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })

      const cardA = container.querySelector<HTMLElement>('[data-card-id="a"]')
      if (cardA === null) throw new Error("card 'a' not found")
      const figureWrappers = Array.from(cardA.querySelectorAll<HTMLElement>(".grid.grid-cols-1.md\\:grid-cols-2 > div"))
      expect(figureWrappers).toHaveLength(2)
      expect(figureWrappers[0].className).toContain("md:col-span-2") // thread
      expect(figureWrappers[1].className).not.toContain("md:col-span-2") // bar
    })

    // Task 21: a thread figure or four-plus figures makes a table "featured"
    // — dense enough to want its own page instead of a shared scroll — so it
    // shouldn't render on the overview at all.
    test("a table with a thread figure or four figures is featured and absent from the overview", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, {
        ...multiTableProps(resolve),
        tables: [
          makeTable("chat", { visualizations: [threadViz()] }),
          makeTable("views", { visualizations: [bar(), bar(), bar(), bar()] }),
          makeTable("account", { visualizations: [] }),
        ],
      })

      const overviewChip = container.querySelector<HTMLElement>("[data-overview-chip]")
      if (overviewChip === null) throw new Error("overview chip not found")
      expect(overviewChip.textContent).toMatch(/Overview|Overzicht/)
      expect(overviewChip.getAttribute("aria-current")).toBe("page")
      expect(container.querySelector('[data-card-id="account"]')).not.toBeNull()
      expect(container.querySelector('[data-card-id="chat"]')).toBeNull()
      expect(container.querySelector('[data-card-id="views"]')).toBeNull()
    })

    // The overview is page 1, so with two featured tables (chat, views) the
    // "views" page is page 3 of 3 — the pager counts every page, not just
    // the featured ones.
    test("a featured chip mounts only that table, with previous/next among featured tables", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, {
        ...multiTableProps(resolve),
        tables: [
          makeTable("chat", { visualizations: [threadViz()] }),
          makeTable("views", { visualizations: [bar(), bar(), bar(), bar()] }),
          makeTable("account", { visualizations: [] }),
        ],
      })

      act(() => {
        container.querySelector('[data-page-chip="views"]')!.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })

      expect(container.querySelector('[data-card-id="views"]')).not.toBeNull()
      expect(container.querySelector('[data-card-id="account"]')).toBeNull()
      expect(container.querySelector("[data-pager]")!.textContent).toContain("3 of 3")

      const previousButton = container.querySelector<HTMLButtonElement>('button[aria-label="Previous"]')
      if (previousButton === null) throw new Error("Previous button not found")
      act(() => {
        previousButton.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })

      expect(container.querySelector('[data-card-id="chat"]')).not.toBeNull()
    })

    test("a featured page falls back to the overview when a new upload drops that table", () => {
      const resolve = jest.fn()
      const props = {
        ...multiTableProps(resolve),
        tables: [
          makeTable("chat", { visualizations: [threadViz()] }),
          makeTable("account", { visualizations: [] }),
        ],
      }
      root = renderConsentFormViz(container, props)
      act(() => {
        container.querySelector('[data-page-chip="chat"]')!.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })
      expect(container.querySelector('[data-card-id="chat"]')).not.toBeNull()

      // The host sends a new tables array (a fresh upload) without "chat".
      act(() => {
        root!.render(<ConsentFormViz {...props} tables={[makeTable("account", { visualizations: [] })]} />)
      })

      expect(container.querySelector('[data-card-id="account"]')).not.toBeNull()
      expect(container.querySelector("[data-overview-chip]")!.getAttribute("aria-current")).toBe("page")
    })

    // Fix round 1: the review is a sequence of equal pages — page 1 is the
    // overview, pages 2..n are the featured tables — and one pager drives
    // all of it. Fix round 2 (variant A): the count reads "i of n", no
    // "page" word.
    test("the pager shows 1 of n on the overview and the featured chips switch pages", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, {
        ...multiTableProps(resolve),
        tables: [makeTable("chat", { visualizations: [threadViz()] }), makeTable("account", { visualizations: [] })],
      })

      expect(container.querySelector("[data-pager]")!.textContent).toContain("1 of 2")

      act(() => {
        container.querySelector('[data-page-chip="chat"]')!.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })

      expect(container.querySelector('[data-card-id="chat"]')).not.toBeNull()
      expect(container.querySelector("[data-pager]")!.textContent).toContain("2 of 2")

      const previousButton = container.querySelector<HTMLButtonElement>('button[aria-label="Previous"]')
      if (previousButton === null) throw new Error("Previous button not found")
      act(() => {
        previousButton.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })

      expect(container.querySelector('[data-card-id="account"]')).not.toBeNull()
      expect(container.querySelector("[data-overview-chip]")!.getAttribute("aria-current")).toBe("page")
    })

    test("with no featured table the pager reads 1 of 1 with both buttons disabled", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, multiTableProps(resolve))

      expect(container.querySelector("[data-pager]")!.textContent).toContain("1 of 1")

      const previousButton = container.querySelector<HTMLButtonElement>('button[aria-label="Previous"]')
      const nextButton = container.querySelector<HTMLButtonElement>('button[aria-label="Next"]')
      if (previousButton === null || nextButton === null) throw new Error("pager buttons not found")

      expect(previousButton.disabled).toBe(true)
      expect(nextButton.disabled).toBe(true)
    })

    // Fix round 2 (variant A): the old grouped-chip pill strip became a
    // plain-text "Jump to" line, overview only — data-chip-id lives inside
    // it now, not in a separate row.
    test("the jump line lists the grouped tables on the overview and is absent on a featured page", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, {
        ...multiTableProps(resolve),
        tables: [makeTable("chat", { visualizations: [threadViz()] }), makeTable("account", { visualizations: [] })],
      })

      expect(container.querySelector('[data-jump] [data-chip-id="account"]')).not.toBeNull()

      act(() => {
        container.querySelector('[data-page-chip="chat"]')!.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })

      expect(container.querySelector("[data-jump]")).toBeNull()
    })

    test("empty tables sink to the end of the page", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, multiTableProps(resolve))

      const cards = Array.from(container.querySelectorAll<HTMLElement>("[data-card-id]"))
      expect(cards.map((c) => c.dataset.cardId)).toEqual(["a", "c", "b"])
    })

    // Tables above the auto-expand threshold (see REVIEW_AUTO_EXPAND_THRESHOLD
    // in table_container.tsx) start collapsed — a dedicated large table here,
    // not `multiTableProps`' 2/0/3-row set, all of which now start expanded.
    test("a large table is collapsed by default and expands on click", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, {
        ...multiTableProps(resolve),
        tables: [tableWithRows("a", "Alpha table", 998)],
      })

      const cardA = container.querySelector<HTMLElement>('[data-card-id="a"]')
      if (cardA === null) throw new Error("card 'a' not found")

      const tableRegion = cardA.querySelector<HTMLElement>(".grid.grid-cols-1.overflow-hidden")
      if (tableRegion === null) throw new Error("table region not found")
      const toggle = cardA.querySelector<HTMLButtonElement>("button[aria-expanded]")
      if (toggle === null) throw new Error("show/hide toggle not found")

      expect(toggle.getAttribute("aria-expanded")).toBe("false")
      expect(tableRegion.style.gridTemplateRows).toBe("0rem")

      act(() => {
        toggle.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })

      expect(toggle.getAttribute("aria-expanded")).toBe("true")
      expect(tableRegion.style.gridTemplateRows).not.toBe("0rem")
    })

    // A small table (<=25 rows) has nothing to gain from collapsing — hiding
    // a 3-row table hides everything for no benefit — so review mode starts
    // it expanded instead of behind the toggle.
    test("a small table (3 rows) starts expanded", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, {
        ...multiTableProps(resolve),
        tables: [tableWithRows("c", "Gamma table", 3)],
      })

      const cardC = container.querySelector<HTMLElement>('[data-card-id="c"]')
      if (cardC === null) throw new Error("card 'c' not found")

      const tableRegion = cardC.querySelector<HTMLElement>(".grid.grid-cols-1.overflow-hidden")
      if (tableRegion === null) throw new Error("table region not found")
      const toggle = cardC.querySelector<HTMLButtonElement>("button[aria-expanded]")
      if (toggle === null) throw new Error("show/hide toggle not found")

      expect(toggle.getAttribute("aria-expanded")).toBe("true")
      expect(tableRegion.style.gridTemplateRows).not.toBe("0rem")
    })

    // Regression: an unlabelled icon-only toggle at common window widths read
    // as a second search button (Danielle: "I don't actually see any
    // tables"). The accessible name must carry the row count at every width,
    // so its label element can never fall back to a `hidden` class.
    test("the toggle button's accessible name includes the row count and its label is never hidden", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, {
        ...multiTableProps(resolve),
        tables: [tableWithRows("a", "Alpha table", 998)],
      })

      const cardA = container.querySelector<HTMLElement>('[data-card-id="a"]')
      if (cardA === null) throw new Error("card 'a' not found")
      const toggle = cardA.querySelector<HTMLButtonElement>("button[aria-expanded]")
      if (toggle === null) throw new Error("show/hide toggle not found")

      expect(toggle.textContent).toContain("998")

      const label = Array.from(toggle.querySelectorAll<HTMLElement>("span")).find((el) =>
        el.textContent?.includes("998")
      )
      if (label === undefined) throw new Error("toggle label element not found")
      expect(label.className.split(/\s+/)).not.toContain("hidden")
    })

    // Regression: a table emptied by the participant's own deletions must
    // keep Undo reachable — the compact "no entries" card is only for tables
    // that were empty from the start (deletedRowCount === 0).
    test("a table emptied by deletion keeps Undo, which restores its rows", () => {
      const resolve = jest.fn()
      root = renderConsentFormViz(container, multiTableProps(resolve))

      let cardA = container.querySelector<HTMLElement>('[data-card-id="a"]')
      if (cardA === null) throw new Error("card 'a' not found")

      // Row checkboxes and the delete control are in the DOM regardless of
      // show/hide state (only the CSS grid height collapses) — toggling here
      // just exercises the control, it isn't a precondition for what follows.
      const toggle = cardA.querySelector<HTMLButtonElement>("button[aria-expanded]")
      if (toggle === null) throw new Error("show/hide toggle not found")
      act(() => {
        toggle.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })

      const selectAll = cardA.querySelector<HTMLElement>("#selectAll")
      if (selectAll === null) throw new Error("select-all checkbox not found")
      act(() => {
        selectAll.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })

      const deleteControl = Array.from(cardA.querySelectorAll<HTMLElement>("div")).find((el) =>
        el.textContent?.trim().startsWith("Delete")
      )
      if (deleteControl === undefined) throw new Error("delete control not found")
      act(() => {
        deleteControl.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })

      // Table 'a' is now empty by deletion (not born empty) — re-query since
      // TableContainer swaps to the compact empty-state markup.
      cardA = container.querySelector<HTMLElement>('[data-card-id="a"]')
      if (cardA === null) throw new Error("card 'a' not found after delete")
      expect(cardA.textContent).not.toContain("No entries in this export")

      const undoButton = cardA.querySelector<HTMLImageElement>("img")
      if (undoButton === null) throw new Error("Undo control not found after deleting all rows")

      act(() => {
        undoButton.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      })

      cardA = container.querySelector<HTMLElement>('[data-card-id="a"]')
      if (cardA === null) throw new Error("card 'a' not found after undo")
      expect(cardA.querySelector("button[aria-expanded]")).not.toBeNull()
      expect(cardA.textContent).toContain("row-0")
    })
  })
})
