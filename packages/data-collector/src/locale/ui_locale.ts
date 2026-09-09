import { useSyncExternalStore } from "react"
import {
  normalizeLocale,
  DEFAULT_UI_LOCALE,
  PROVISIONAL_UI_LOCALES,
  SUPPORTED_UI_LOCALES,
} from "./policy"

/**
 * Where a participant's language choice is kept between visits.
 *
 * Namespaced, because the education tool is served from a Pages origin that other things
 * may share.
 */
export const UI_LOCALE_STORAGE_KEY = "dfe.locale"

/** A locale is offered when it is supported and not provisional. */
function hasStudyContent(locale: string): boolean {
  return !PROVISIONAL_UI_LOCALES.includes(locale)
}

/**
 * The locales the toggle offers, derived from `ui_locales.json` rather than listed again.
 *
 * A provisional locale has machine-translated chrome and no reviewed study content, so
 * choosing one would render the tool's own buttons in that language and every table
 * title in English. Filtering the supported set by that same `provisional` key keeps this
 * list in step with ADR-0038's single declaration: adding `fr` to `ui_locales.json`
 * offers it here the moment it stops being provisional, and nothing here has to be
 * edited to match.
 */
export const OFFERED_UI_LOCALES: readonly string[] = SUPPORTED_UI_LOCALES.filter(hasStudyContent)

function isOffered(value: unknown): value is string {
  return typeof value === "string" && OFFERED_UI_LOCALES.includes(value)
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

/**
 * Record a new language preference and re-render the toggles showing it.
 *
 * This is a *preference*, not a live switch: the tool page reads the stored value once
 * when it mounts and holds it for the session (see `App.tsx`), so a change made here
 * takes effect the next time the tool is opened. Re-rendering the tool on a locale change
 * is not an option — `ScriptHostComponent`'s effect lists `locale`, and remounting that
 * effect restarts the tool from its first page, so the participant loses their place.
 */
export function setUiLocale(locale: string): void {
  if (!isOffered(locale) || locale === snapshot()) return
  current = locale
  writeStored(locale)
  listeners.forEach((listener) => {
    listener()
  })
}

/**
 * The stored language preference, read without subscribing to changes.
 *
 * What `App.tsx` calls once on mount. A module-level store rather than a context because
 * the navbar and the tool page sit in different route elements with no common ancestor to
 * hang a provider on.
 */
export function readUiLocale(): string {
  return snapshot()
}

/**
 * The current language preference, re-rendering the caller when it changes.
 *
 * For the toggle itself, which has to show which language is selected. Not for the tool
 * page — see `setUiLocale`.
 */
export function useUiLocale(): string {
  return useSyncExternalStore(subscribe, snapshot, snapshot)
}

/** Test seam: forget the resolved locale so the next read resolves it again. */
export function resetUiLocaleForTest(): void {
  current = null
}
