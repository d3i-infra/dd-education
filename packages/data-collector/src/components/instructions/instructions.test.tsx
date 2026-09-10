/** @jest-environment jsdom */
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { Instructions, PropsUIPromptInstructions } from "./instructions"
import { ReactFactoryContext } from "@eyra/feldspar"

// React 19 gates `act()` warnings behind this global instead of
// react-dom/test-utils — see issue_form.test.tsx for the same setup.
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

type Props = PropsUIPromptInstructions & ReactFactoryContext

function baseProps(resolve: (payload: any) => void): Props {
  return {
    __type__: "PropsUIPromptInstructions",
    description: { translations: { en: "Follow these steps", nl: "Volg deze stappen" } },
    imageUrl: "",
    locale: "en",
    resolve,
  }
}

function renderInstructions(container: HTMLDivElement, props: Props): Root {
  const root = createRoot(container)
  act(() => {
    root.render(<Instructions {...props} />)
  })
  return root
}

function getContinueButton(container: HTMLDivElement): HTMLElement {
  const button = container.querySelector<HTMLElement>("#confirm-button")
  if (button === null) throw new Error("continue button not found")
  return button
}

function clickButton(el: HTMLElement): void {
  act(() => {
    el.dispatchEvent(new MouseEvent("click", { bubbles: true }))
  })
}

describe("Instructions", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement("div")
    document.body.appendChild(container)
    // jsdom has no scrollTo implementation; the component calls it on mount.
    window.scrollTo = jest.fn()
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  describe("single image (no deck)", () => {
    test("renders the image and Continue resolves", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, {
        ...baseProps(resolve),
        imageUrl: "netflix_instructions.webp",
      })

      const img = container.querySelector("img")
      expect(img?.getAttribute("src")).toBe("netflix_instructions.webp")
      expect(img?.getAttribute("alt")).toBe("Instructions")

      // No stepper controls for a single image.
      expect(container.querySelector('[aria-label="Step 1"]')).toBeNull()

      clickButton(getContinueButton(container))
      expect(resolve).toHaveBeenCalledWith({ __type__: "PayloadString", value: "continue" })
    })
  })

  describe("step deck (imageUrls with more than one entry)", () => {
    const steps = ["instructions/chatgpt/step-01.webp", "instructions/chatgpt/step-02.webp", "instructions/chatgpt/step-03.webp"]

    function deckProps(resolve: (payload: any) => void): Props {
      return { ...baseProps(resolve), imageUrls: steps }
    }

    test("renders step 1 of M with the first image", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, deckProps(resolve))

      expect(container.textContent).toContain("Step 1 of 3")
      const img = container.querySelector("img")
      expect(img?.getAttribute("src")).toBe(steps[0])
      expect(img?.getAttribute("alt")).toBe("Step 1")
    })

    test("the step counter is an aria-live region, so navigation is announced", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, deckProps(resolve))

      const counter = Array.from(container.querySelectorAll("div")).find((el) =>
        el.textContent?.trim() === "Step 1 of 3"
      )
      if (counter === undefined) throw new Error("step counter element not found")
      expect(counter.getAttribute("aria-live")).toBe("polite")
      expect(counter.getAttribute("aria-atomic")).toBe("true")
    })

    test("Next advances to the next step", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, deckProps(resolve))

      const nextButton = Array.from(container.querySelectorAll("button")).find((b) => b.textContent === "Next")
      if (nextButton === undefined) throw new Error("Next button not found")

      clickButton(nextButton)

      expect(container.textContent).toContain("Step 2 of 3")
      const img = container.querySelector("img")
      expect(img?.getAttribute("src")).toBe(steps[1])
      expect(img?.getAttribute("alt")).toBe("Step 2")
    })

    test("Previous is disabled on step 1 and enabled after advancing", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, deckProps(resolve))

      const previousButton = Array.from(container.querySelectorAll("button")).find((b) => b.textContent === "Previous") as HTMLButtonElement
      expect(previousButton.disabled).toBe(true)

      const nextButton = Array.from(container.querySelectorAll("button")).find((b) => b.textContent === "Next") as HTMLButtonElement
      clickButton(nextButton)

      expect(previousButton.disabled).toBe(false)
    })

    test("right arrow key advances to the next step", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, deckProps(resolve))

      act(() => {
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }))
      })

      expect(container.textContent).toContain("Step 2 of 3")
    })

    test("left arrow key moves back to the previous step", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, deckProps(resolve))

      act(() => {
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }))
      })
      act(() => {
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft" }))
      })

      expect(container.textContent).toContain("Step 1 of 3")
    })

    test("a dot jumps directly to its step", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, deckProps(resolve))

      const dot = container.querySelector<HTMLButtonElement>('[aria-label="Step 3"]')
      if (dot === null) throw new Error("dot for step 3 not found")
      clickButton(dot)

      expect(container.textContent).toContain("Step 3 of 3")
      const img = container.querySelector("img")
      expect(img?.getAttribute("src")).toBe(steps[2])
    })

    test("renders one dot per step", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, deckProps(resolve))

      const dots = container.querySelectorAll("[aria-label^='Step ']")
      expect(dots).toHaveLength(3)
    })

    test("Continue still resolves from within the stepper", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, deckProps(resolve))

      clickButton(getContinueButton(container))
      expect(resolve).toHaveBeenCalledWith({ __type__: "PayloadString", value: "continue" })
    })
  })

  describe("export link", () => {
    test("renders a link to the platform's export page above the images when linkUrl is set", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, {
        ...baseProps(resolve),
        imageUrl: "a.webp",
        linkUrl: "https://example.test/export",
      })

      const link = container.querySelector("a")
      if (link === null) throw new Error("export link not found")
      expect(link.getAttribute("href")).toBe("https://example.test/export")
      expect(link.getAttribute("target")).toBe("_blank")
      expect(link.getAttribute("rel")).toBe("noopener noreferrer")
    })

    test("renders no link when linkUrl is empty", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, {
        ...baseProps(resolve),
        imageUrl: "a.webp",
        linkUrl: "",
      })

      expect(container.querySelector("a")).toBeNull()
    })

    test("renders no link when linkUrl is not provided", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, {
        ...baseProps(resolve),
        imageUrl: "a.webp",
      })

      expect(container.querySelector("a")).toBeNull()
    })
  })

  describe("export note", () => {
    const note = { translations: { en: "Login note.", nl: "Login notitie." } }

    test("renders the note in the current locale when given", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, {
        ...baseProps(resolve),
        imageUrl: "a.webp",
        linkUrl: "https://example.test/export",
        linkNote: note,
        locale: "nl",
      })

      const p = container.querySelector("p")
      expect(p?.textContent).toBe("Login notitie.")
    })

    test("renders no note when linkNote is null", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, {
        ...baseProps(resolve),
        imageUrl: "a.webp",
        linkUrl: "https://example.test/export",
        linkNote: null,
      })

      expect(container.querySelector("p")).toBeNull()
    })

    test("renders no note when linkNote is not provided", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, {
        ...baseProps(resolve),
        imageUrl: "a.webp",
        linkUrl: "https://example.test/export",
      })

      expect(container.querySelector("p")).toBeNull()
    })
  })

  describe("a single-entry imageUrls list", () => {
    test("behaves like a single image, not a stepper", () => {
      const resolve = jest.fn()
      root = renderInstructions(container, {
        ...baseProps(resolve),
        imageUrls: ["instructions/chatgpt/step-01.webp"],
      })

      expect(container.querySelector('[aria-label^="Step "]')).toBeNull()
      expect(container.textContent).not.toContain("Step 1 of 1")
      const img = container.querySelector("img")
      expect(img?.getAttribute("src")).toBe("instructions/chatgpt/step-01.webp")
      expect(img?.getAttribute("alt")).toBe("Instructions")
    })
  })
})
