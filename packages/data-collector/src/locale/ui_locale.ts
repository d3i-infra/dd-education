import { useSyncExternalStore } from "react"
import { normalizeLocale, DEFAULT_UI_LOCALE } from "./policy"

/**
 * Where a participant's language choice is kept between visits.
 *
 * Namespaced, because the education tool is served from a Pages origin that other things
 * may share.
 */
export const UI_LOCALE_STORAGE_KEY = "dfe.locale"

/**
 * The locales the toggle offers.
 *
 * `SUPPORTED_UI_LOCALES` lists five, but only `en` and `nl` have study content written
 * for them (`de`, `it` and `es` are provisional chrome-only locales); offering a language
 * whose tables would all render in English would be a worse experience than not offering
 * it.
 */
export const OFFERED_UI_LOCALES = ["en", "nl"] as const

export type OfferedUiLocale = (typeof OFFERED_UI_LOCALES)[number]

function isOffered(value: unknown): value is OfferedUiLocale {
  return typeof value === "string" && (OFFERED_UI_LOCALES as readonly string[]).includes(value)
}

/**
 * The locale the tool opens in.
 *
 * A choice the participant made earlier wins outright — they said what they wanted, and
 * a browser configured in another language does not override that. With nothing stored,
 * the browser's own language decides, normalized through the same policy the host's
 * locale goes through, so anything the tool has no content for lands on the default.
 *
 * Pure on purpose: `stored` and `navigatorLanguage` are read by the caller, so the rule
 * itself is testable without a DOM.
 */
export function resolveInitialLocale(stored: unknown, navigatorLanguage: unknown): string {
  if (isOffered(stored)) return stored
  const fromBrowser = normalizeLocale(navigatorLanguage)
  return isOffered(fromBrowser) ? fromBrowser : DEFAULT_UI_LOCALE
}

function readStored(): string | null {
  try {
    return window.localStorage.getItem(UI_LOCALE_STORAGE_KEY)
  } catch {
    // Private mode, blocked site data, no storage at all: not knowing the last choice is
    // a worse first render, not a broken tool.
    return null
  }
}

function writeStored(locale: string): void {
  try {
    window.localStorage.setItem(UI_LOCALE_STORAGE_KEY, locale)
  } catch {
    /* the choice still applies to this visit; it just will not survive it */
  }
}

let current: string | null = null
const listeners = new Set<() => void>()

function snapshot(): string {
  if (current === null) {
    current = resolveInitialLocale(readStored(), globalThis.navigator?.language)
  }
  return current
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Switch the tool's language, remember it, and re-render everything showing it. */
export function setUiLocale(locale: string): void {
  if (!isOffered(locale) || locale === snapshot()) return
  current = locale
  writeStored(locale)
  listeners.forEach((listener) => {
    listener()
  })
}

/**
 * The tool's current UI locale.
 *
 * A module-level store rather than a context, because the two places that show the
 * toggle — the site navbar and the tool page — sit in different route elements with no
 * common ancestor to hang a provider on.
 */
export function useUiLocale(): string {
  return useSyncExternalStore(subscribe, snapshot, snapshot)
}

/** Test seam: forget the resolved locale so the next read resolves it again. */
export function resetUiLocaleForTest(): void {
  current = null
}
