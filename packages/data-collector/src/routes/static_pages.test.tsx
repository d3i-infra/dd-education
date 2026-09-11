/** @jest-environment jsdom */
import { act, type ReactElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { MemoryRouter } from "react-router-dom"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { LandingPage } from "./landing_page"
import { About } from "./about"
import { PrivacyPolicy } from "./privacy_policy"
import { UI_LOCALE_STORAGE_KEY, resetUiLocaleForTest, setUiLocale } from "../locale/ui_locale"

describe("static pages follow the site's en/nl toggle", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    window.localStorage.removeItem(UI_LOCALE_STORAGE_KEY)
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

  function mount(element: ReactElement): void {
    root = createRoot(container)
    act(() => {
      root.render(<MemoryRouter>{element}</MemoryRouter>)
    })
  }

  test("the landing page is English by default and Dutch after the toggle", () => {
    mount(<LandingPage />)
    const h1 = container.querySelector("h1")
    if (h1 === null) throw new Error("h1 not found")
    expect(h1.textContent).toBe("Digital Footprint Explorer")
    expect(container.textContent).toContain("Welcome to Digital Footprint Explorer")

    act(() => {
      setUiLocale("nl")
    })

    expect(container.textContent).toContain("Welkom bij de Digitale Voetafdruk Verkenner")
    const button = container.querySelector('[role="button"]')
    if (button === null) throw new Error("Starten button not found")
    expect(button.textContent?.trim()).toBe("Starten")
  })

  test("the about page switches its headings", () => {
    setUiLocale("nl")
    mount(<About />)
    const h1 = container.querySelector("h1")
    if (h1 === null) throw new Error("h1 not found")
    expect(h1.textContent).toBe("Over de Digitale Voetafdruk Verkenner")

    const h2s = Array.from(container.querySelectorAll("h2")).map((el) => el.textContent)
    expect(h2s).toContain("Wat is datadonatie?")
  })

  test("the privacy page and the navbar switch too", () => {
    setUiLocale("nl")
    mount(<PrivacyPolicy />)
    const h1 = container.querySelector("h1")
    if (h1 === null) throw new Error("h1 not found")
    expect(h1.textContent).toBe("Privacybeleid")

    const link = Array.from(container.querySelectorAll("a")).find(
      (candidate) => candidate.textContent === "Over"
    )
    if (link === undefined) throw new Error("navbar 'Over' link not found")
  })

  test("no formal Dutch anywhere in the site text", async () => {
    const { siteText } = await import("./site_text")
    const nl = Object.values(siteText("nl")).join(" ")
    expect(nl).not.toMatch(/\b[Uu]w\b/)
    expect(nl).not.toMatch(/\bU\b/)
  })

  test("the footer carries the website's partner strip and copyright", () => {
    mount(<LandingPage />)
    const footer = container.querySelector("footer")
    if (footer === null) throw new Error("footer not found")
    expect(footer.textContent).toMatch(/A service provided by/)
    expect(footer.textContent).toMatch(/Project partners/)

    for (const name of [
      "ODISSEI",
      "Eyra",
      "University of Amsterdam",
      "Radboud University",
      "Utrecht University",
      "Vrije Universiteit Amsterdam",
      "Tilburg University",
      "Erasmus University Rotterdam",
    ]) {
      const img = container.querySelector(`img[alt="${name}"]`)
      if (img === null) throw new Error(`logo with alt "${name}" not found`)
    }

    expect(footer.textContent).toContain(`© ${new Date().getFullYear()} datadonation.eu`)

    const privacyLink = Array.from(container.querySelectorAll("a")).find(
      (candidate) => candidate.textContent === "Privacy Policy"
    )
    if (privacyLink === undefined) throw new Error("Privacy Policy link not found")
    expect(privacyLink.getAttribute("href")).toBe("/privacy-policy")
  })

  test("the About page no longer claims all of Europe", () => {
    mount(<About />)
    expect(container.textContent).not.toMatch(/Europe's/)
    expect(container.textContent).toMatch(/Data Donation Infrastructure \(D3I\)/)
  })
})
