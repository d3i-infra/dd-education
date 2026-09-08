/** @jest-environment jsdom */
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { IssueForm } from "./issue_form"
import { PropsUIPromptIssueForm } from "./types"
import { ReactFactoryContext } from "@eyra/feldspar"
import { buildEnv } from "../../build_env"

// React 19 gates `act()` warnings behind this global instead of
// react-dom/test-utils; without it every state update outside a literal
// act() callback (e.g. inside the awaited fetch handler) logs a false
// "not configured to support act" warning.
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

type Props = PropsUIPromptIssueForm & ReactFactoryContext

const baseProps: Props = {
  __type__: "PropsUIPromptIssueForm",
  description: "Something went wrong",
  platform: "netflix",
  tables: [],
  locale: "en",
  resolve: () => {},
}

function renderIssueForm(container: HTMLDivElement, props: Props): Root {
  const root = createRoot(container)
  act(() => {
    root.render(<IssueForm {...props} />)
  })
  return root
}

function getSubmitButton(container: HTMLDivElement): HTMLButtonElement {
  const button = container.querySelector("button")
  if (button === null) throw new Error("submit button not found")
  return button
}

async function clickAndFlush(button: HTMLButtonElement): Promise<void> {
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    // Let the microtask queue (the awaited fetch + its catch/finally) drain.
    await Promise.resolve()
    await Promise.resolve()
  })
}

describe("IssueForm submit button", () => {
  let container: HTMLDivElement
  let root: Root
  let alertSpy: jest.SpyInstance

  beforeEach(() => {
    container = document.createElement("div")
    document.body.appendChild(container)
    alertSpy = jest.spyOn(window, "alert").mockImplementation(() => {})
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    alertSpy.mockRestore()
    jest.restoreAllMocks()
    delete buildEnv.VITE_ISSUE_REPORT_URL
  })

  test("stays enabled for retry when the upload fails", async () => {
    const fetchMock = jest.fn().mockRejectedValue(new Error("network down"))
    globalThis.fetch = fetchMock as unknown as typeof fetch

    root = renderIssueForm(container, baseProps)
    const button = getSubmitButton(container)
    expect(button.disabled).toBe(false)

    await clickAndFlush(button)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(alertSpy).toHaveBeenCalledWith("Upload failed. Please try again later.")
    // The bug: `finally` used to set hasSubmitted(true) unconditionally, so a
    // failed report could never be retried because the button stayed disabled.
    expect(button.disabled).toBe(false)
  })

  test("disables once the upload succeeds", async () => {
    const fetchMock = jest.fn().mockResolvedValue({ ok: true } as Response)
    globalThis.fetch = fetchMock as unknown as typeof fetch

    root = renderIssueForm(container, baseProps)
    const button = getSubmitButton(container)

    await clickAndFlush(button)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(alertSpy).not.toHaveBeenCalled()
    expect(button.disabled).toBe(true)
  })

  test("posts to the study's own worker when no endpoint is configured", async () => {
    // The variable overrides a working default, so a build that sets nothing still
    // reaches the endpoint this study's reports already go to.
    const fetchMock = jest.fn().mockResolvedValue({ ok: true } as Response)
    globalThis.fetch = fetchMock as unknown as typeof fetch

    root = renderIssueForm(container, baseProps)
    await clickAndFlush(getSubmitButton(container))

    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain("https://late-sunset-4214.ncdeschipper.workers.dev?filename=netflix-")
  })

  test("posts to the configured endpoint when the build set one", async () => {
    buildEnv.VITE_ISSUE_REPORT_URL = "https://reports.example.test"
    const fetchMock = jest.fn().mockResolvedValue({ ok: true } as Response)
    globalThis.fetch = fetchMock as unknown as typeof fetch

    root = renderIssueForm(container, baseProps)
    await clickAndFlush(getSubmitButton(container))

    expect(String(fetchMock.mock.calls[0][0])).toContain(
      "https://reports.example.test?filename=netflix-"
    )
  })
})
