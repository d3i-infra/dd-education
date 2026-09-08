/** @jest-environment jsdom */
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

//: Every set of props `ScriptHostComponent` was rendered with, in order.
const hostRenders: Record<string, unknown>[] = []

jest.mock("@eyra/feldspar", () => {
  const actual = jest.requireActual("@eyra/feldspar")
  return {
    // `__esModule` is non-enumerable, so spreading `actual` would drop it and every
    // `import Foo from "@eyra/feldspar"` would resolve to the module object instead of
    // the default export. Re-declare it.
    __esModule: true,
    ...actual,
    // Stands in for the real host so the test can watch the props it is handed without
    // starting a Pyodide worker. Its render count is the assertion that matters: the
    // real component's effect lists `locale` and `factories`, and remounting that effect
    // terminates the worker it has just started while the previous one keeps running.
    ScriptHostComponent: (props: Record<string, unknown>) => {
      hostRenders.push(props)
      return null
    },
    // Neither of these is in the test shim, which re-exports only what a rendering test
    // needs from feldspar's source. A bare class is enough here — App only ever puts
    // instances into the array whose identity is under test.
    DataSubmissionPageFactory: class DataSubmissionPageFactory {},
  }
})

jest.mock("./build_env", () => ({
  buildEnv: { VITE_PLATFORM: "education", DEV: false },
}))

// The consent-viz factory drags in the visualization plugin, whose worker module uses
// `import.meta.url` — unparseable under jest's CommonJS runtime. This test is about what
// App hands the host, not about what the factories do, so a bare class is enough: the
// assertions only ever compare the array's identity.
jest.mock("./factories/consent_form_viz", () => ({
  ConsentFormVizFactory: class ConsentFormVizFactory {},
}))

import App from "./App"
import { UI_LOCALE_STORAGE_KEY, resetUiLocaleForTest, setUiLocale } from "./locale/ui_locale"

describe("the education tool page", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    window.localStorage.clear()
    resetUiLocaleForTest()
    hostRenders.length = 0
    container = document.createElement("div")
    document.body.appendChild(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  function render() {
    root = createRoot(container)
    act(() => {
      root.render(<App />)
    })
  }

  test("shows no language toggle of its own", () => {
    // The toggle lives in the site navbar. Putting one here would let a participant
    // change `locale` mid-session, which is the prop whose change leaks a worker.
    render()
    expect(container.querySelector('[aria-label="Language"]')).toBeNull()
    expect(container.querySelectorAll("button")).toHaveLength(0)
  })

  test("takes the stored preference as its locale", () => {
    window.localStorage.setItem(UI_LOCALE_STORAGE_KEY, "nl")
    render()
    expect(hostRenders[0].locale).toBe("nl")
  })

  test("holds that locale even when the preference changes underneath it", () => {
    window.localStorage.setItem(UI_LOCALE_STORAGE_KEY, "nl")
    render()
    expect(hostRenders).toHaveLength(1)

    act(() => {
      setUiLocale("en")
    })

    // Not re-rendered at all, so `locale` cannot have changed identity: the host's effect
    // never remounts and the one worker it started stays the one that is running.
    expect(hostRenders).toHaveLength(1)
    expect(hostRenders[0].locale).toBe("nl")
    // The new preference is still recorded — it applies the next time the tool opens.
    expect(window.localStorage.getItem(UI_LOCALE_STORAGE_KEY)).toBe("en")
  })

  test("hands the host the same factories array on every render", () => {
    render()
    const first = hostRenders[0].factories
    act(() => {
      root.render(<App />)
    })
    expect(hostRenders).toHaveLength(2)
    expect(hostRenders[1].factories).toBe(first)
    expect(hostRenders[1].locale).toBe(hostRenders[0].locale)
  })
})
