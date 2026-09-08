/** @jest-environment jsdom */
import {
  OFFERED_UI_LOCALES,
  UI_LOCALE_STORAGE_KEY,
  resolveInitialLocale,
  resetUiLocaleForTest,
  setUiLocale,
} from "./ui_locale"
import { DEFAULT_UI_LOCALE } from "./policy"

describe("resolveInitialLocale", () => {
  it("uses a stored choice whatever the browser says", () => {
    expect(resolveInitialLocale("nl", "en-GB")).toBe("nl")
    expect(resolveInitialLocale("en", "nl-NL")).toBe("en")
  })

  it("falls back to the browser's language when nothing is stored", () => {
    expect(resolveInitialLocale(null, "nl-NL")).toBe("nl")
    expect(resolveInitialLocale(null, "nl")).toBe("nl")
    expect(resolveInitialLocale(null, "NL_nl")).toBe("nl")
  })

  it("lands on the default for a language the tool has no content for", () => {
    expect(resolveInitialLocale(null, "fr-FR")).toBe(DEFAULT_UI_LOCALE)
    expect(resolveInitialLocale(null, "ro")).toBe(DEFAULT_UI_LOCALE)
  })

  it("ignores a stored value the toggle does not offer", () => {
    // A provisional locale has chrome but no study content, so a stale or hand-edited
    // storage entry must not strand a participant on half-translated tables.
    expect(resolveInitialLocale("de", "nl-NL")).toBe("nl")
    expect(resolveInitialLocale("de", "fr-FR")).toBe(DEFAULT_UI_LOCALE)
    expect(resolveInitialLocale("nl-NL", "en")).toBe(DEFAULT_UI_LOCALE)
  })

  it("survives a browser that reports no language at all", () => {
    expect(resolveInitialLocale(null, undefined)).toBe(DEFAULT_UI_LOCALE)
    expect(resolveInitialLocale(null, "")).toBe(DEFAULT_UI_LOCALE)
    expect(resolveInitialLocale(undefined, null)).toBe(DEFAULT_UI_LOCALE)
  })

  it("offers exactly the two locales that have study content", () => {
    expect([...OFFERED_UI_LOCALES]).toEqual(["en", "nl"])
  })

  it("namespaces what it stores", () => {
    expect(UI_LOCALE_STORAGE_KEY).toBe("dfe.locale")
  })
})

describe("the stored choice", () => {
  beforeEach(() => {
    window.localStorage.clear()
    resetUiLocaleForTest()
  })

  it("is written under the namespaced key when a participant switches", () => {
    setUiLocale("nl")
    expect(window.localStorage.getItem(UI_LOCALE_STORAGE_KEY)).toBe("nl")
  })

  it("is not written for a locale the toggle does not offer", () => {
    setUiLocale("de")
    expect(window.localStorage.getItem(UI_LOCALE_STORAGE_KEY)).toBeNull()
  })

  it("comes back on the next load", () => {
    setUiLocale("nl")
    resetUiLocaleForTest()
    expect(resolveInitialLocale(window.localStorage.getItem(UI_LOCALE_STORAGE_KEY), "en-GB")).toBe("nl")
  })

  it("survives storage that refuses to be written", () => {
    const setItem = jest
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("site data blocked")
      })

    expect(() => {
      setUiLocale("nl")
    }).not.toThrow()

    setItem.mockRestore()
  })
})
