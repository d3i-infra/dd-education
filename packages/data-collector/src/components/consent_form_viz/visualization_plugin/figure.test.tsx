/** @jest-environment jsdom */
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"

// Only useVisualizationData.tsx constructs a Web Worker with
// `new Worker(new URL(..., import.meta.url))` -- syntax Jest's CJS-hybrid
// ts-jest transform cannot parse (see consent_form_viz.test.tsx, which mocks
// Figure wholesale for the same reason). Mocking just the hook here lets the
// real FigureComponent -- the wrapper markup this file exists to test --
// render for real, fed canned data/status instead of a real worker round trip.
jest.mock("./visualizationDataFunctions/useVisualizationData", () => ({
  __esModule: true,
  default: jest.fn(),
}))

import useVisualizationData from "./visualizationDataFunctions/useVisualizationData"
import { FigureComponent, ValidatedFigureProps } from "./figure"
import { HeatmapVisualization, HeatmapVisualizationData, Table, ThreadVisualization, ThreadVisualizationData } from "./types"

// React 19 gates `act()` warnings behind this global instead of
// react-dom/test-utils -- see issue_form.test.tsx for the same setup.
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const mockUseVisualizationData = useVisualizationData as jest.Mock

function makeTable(): Table {
  return { id: "t1", head: { cells: ["a"] }, body: { rows: [{ id: "r1", cells: ["x"] }] } }
}

function renderFigure(container: HTMLDivElement, props: Omit<ValidatedFigureProps, "table" | "handleDelete" | "handleUndo">): Root {
  const root = createRoot(container)
  act(() => {
    root.render(
      <FigureComponent
        table={makeTable()}
        visualization={props.visualization}
        locale={props.locale}
        handleDelete={() => {}}
        handleUndo={() => {}}
      />
    )
  })
  return root
}

function figureRow(container: HTMLDivElement): HTMLElement {
  const row = container.querySelector<HTMLElement>("[data-figure-row]")
  if (row === null) throw new Error("figure row not found")
  return row
}

function cardWrapper(container: HTMLDivElement): HTMLElement {
  const wrapper = container.firstElementChild as HTMLElement | null
  if (wrapper === null) throw new Error("card wrapper not found")
  return wrapper
}

describe("FigureComponent height/overflow wrapper", () => {
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
    jest.resetAllMocks()
  })

  test("a thread figure with no explicit height gets h-auto, no fixed gridTemplateRows, and no overflow-hidden on the card", () => {
    const threadData: ThreadVisualizationData = {
      type: "thread",
      threads: [{ id: "0", title: "A", count: 1, turns: [{ role: "user", text: "hi" }] }],
      truncated: false,
      totalThreads: 1,
      pageSize: { threads: 20, turns: 50 },
    }
    mockUseVisualizationData.mockReturnValue([threadData, "success"])
    const visualization: ThreadVisualization = {
      title: {}, type: "thread", groupColumn: "a", roleColumn: "a", textColumn: "a",
    }

    root = renderFigure(container, { visualization, locale: "en" })

    const row = figureRow(container)
    expect(row.className).toContain("h-auto")
    expect(row.style.gridTemplateRows).toBe("")
    expect(cardWrapper(container).className).not.toMatch(/\boverflow-hidden\b/)
  })

  test("a thread figure with an explicit height keeps the fixed-row behaviour (explicit height is honoured)", () => {
    const threadData: ThreadVisualizationData = {
      type: "thread", threads: [], truncated: false, totalThreads: 0, pageSize: { threads: 20, turns: 50 },
    }
    mockUseVisualizationData.mockReturnValue([threadData, "success"])
    const visualization: ThreadVisualization = {
      title: {}, type: "thread", groupColumn: "a", roleColumn: "a", textColumn: "a", height: 300,
    }

    root = renderFigure(container, { visualization, locale: "en" })

    const row = figureRow(container)
    expect(row.className).not.toContain("h-auto")
    expect(row.style.gridTemplateRows).toBe("300px")
    expect(cardWrapper(container).className).toMatch(/\boverflow-hidden\b/)
  })

  test("a non-thread figure (heatmap) keeps the default fixed-height, overflow-hidden card -- unaffected by the thread carve-out", () => {
    const heatmapData: HeatmapVisualizationData = { type: "heatmap", mode: "calendar", max: 0, grids: [] }
    mockUseVisualizationData.mockReturnValue([heatmapData, "success"])
    const visualization: HeatmapVisualization = { title: {}, type: "heatmap", mode: "calendar", dateColumn: "a" }

    root = renderFigure(container, { visualization, locale: "en" })

    const row = figureRow(container)
    expect(row.className).not.toContain("h-auto")
    expect(row.style.gridTemplateRows).toBe("250px") // default height
    expect(cardWrapper(container).className).toMatch(/\boverflow-hidden\b/)
  })
})
