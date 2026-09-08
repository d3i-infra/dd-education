/** @jest-environment jsdom */
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { createMemoryRouter, RouterProvider } from "react-router-dom"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { RouteError } from "./route_error"
import { UI_LOCALE_STORAGE_KEY, resetUiLocaleForTest } from "../locale/ui_locale"

function Thrower(): never {
  throw new Error("boom from a broken component")
}

function renderRouted(container: HTMLDivElement): Root {
  const router = createMemoryRouter(
    [{ path: "/", element: <Thrower />, errorElement: <RouteError /> }],
    { initialEntries: ["/"] }
  )
  const root = createRoot(container)
  act(() => {
    root.render(<RouterProvider router={router} />)
  })
  return root
}

describe("RouteError", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    window.localStorage.clear()
    resetUiLocaleForTest()
    container = document.createElement("div")
    document.body.appendChild(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  test("shows the English message, the error's message, and a link back to the platforms", () => {
    root = renderRouted(container)

    expect(container.textContent).toContain("Something went wrong while showing this page.")
    expect(container.textContent).toContain("boom from a broken component")
    // No stack trace leaks into the page.
    expect(container.textContent).not.toContain("route_error.test")

    const link = container.querySelector("a")
    if (link === null) throw new Error("back link not found")
    expect(link.textContent).toBe("Back to the platforms")
    expect(link.getAttribute("href")).toBe("/port")
  })

  test("shows the Dutch message when that is the stored preference", () => {
    window.localStorage.setItem(UI_LOCALE_STORAGE_KEY, "nl")
    root = renderRouted(container)

    expect(container.textContent).toContain("Er ging iets mis bij het tonen van deze pagina.")
    const link = container.querySelector("a")
    if (link === null) throw new Error("back link not found")
    expect(link.textContent).toBe("Terug naar de platforms")
  })
})
