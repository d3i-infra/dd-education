/** @jest-environment jsdom */
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"

// table_container.tsx pulls in the visualization_plugin subtree, which
// constructs a Web Worker via `new Worker(new URL(..., import.meta.url))` —
// syntax Jest's CJS-hybrid ts-jest transform cannot parse (see
// useVisualizationData.tsx). This test exercises ConsentFormViz's own
// description/button/resolve logic, not table rendering, so the real
// TableContainer (and that unrenderable subtree) is replaced with a stub.
jest.mock("./table_container", () => ({
  TableContainer: () => null,
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
  })
})
