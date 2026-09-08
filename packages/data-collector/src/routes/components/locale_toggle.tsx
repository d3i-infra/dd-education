import { OFFERED_UI_LOCALES, setUiLocale, useUiLocale } from "../../locale/ui_locale"

/** What each offered locale calls itself. */
const LABELS: Record<string, string> = {
  en: "English",
  nl: "Nederlands",
}

const SHORT: Record<string, string> = {
  en: "EN",
  nl: "NL",
}

/**
 * The tool's language switch.
 *
 * Two buttons rather than a select, so both languages are visible at a glance and one
 * click switches; each is labelled in its own language, because a participant looking for
 * Dutch is not helped by the word "Dutch".
 */
export const LocaleToggle = () => {
  const locale = useUiLocale()

  return (
    <div className="flex items-center gap-1" role="group" aria-label="Language">
      {OFFERED_UI_LOCALES.map((offered) => {
        const isCurrent = offered === locale
        return (
          <button
            key={offered}
            type="button"
            lang={offered}
            aria-label={LABELS[offered]}
            aria-pressed={isCurrent}
            onClick={() => {
              setUiLocale(offered)
            }}
            className={
              "px-2 py-1 text-sm rounded-md transition-colors duration-200 " +
              (isCurrent
                ? "bg-primary text-white font-medium"
                : "text-grey2 hover:bg-primarylight hover:text-primary")
            }
          >
            {SHORT[offered]}
          </button>
        )
      })}
    </div>
  )
}
