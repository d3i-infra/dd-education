import { DataSubmissionPageFactory, ScriptHostComponent } from "@eyra/feldspar";
import { ConsentFormVizFactory } from "./factories/consent_form_viz";
import { FileInputMultipleFactory } from "./components/file_input_multiple/factory"
import { ErrorPageFactory } from "./components/error_page/factory"
import { QuestionnaireFactory } from "./components/questionnaire/factory"
import { RetryPromptFactory } from "./components/retry_prompt/factory"
import { IssueFormFactory } from "./components/issue_form/factory"
import { PlatformSelectionFactory } from "./components/platform_selection/factory"
import { InstructionsFactory } from "./components/instructions/factory"
import { normalizeLocale, DEFAULT_UI_LOCALE } from "./locale/policy"
import { useUiLocale } from "./locale/ui_locale"
import { LocaleToggle } from "./routes/components/locale_toggle"
import { buildEnv } from "./build_env"

// DEV-gated query param: the Playwright e2e injection point. Production locale
// comes only from mono's live-init (LiveBridge), never from the URL.
const devLocale = buildEnv.DEV
  ? new URLSearchParams(window.location.search).get('locale') ?? undefined
  : undefined

// The education tool is served standalone (ADR-0041): there is no host to send a locale,
// so it picks its own — the participant's stored choice, else their browser's language.
// A study build keeps handing that decision to mono's live-init, so it passes nothing.
const isEducation = buildEnv.VITE_PLATFORM === "education"

const LoadingScreen = (
  <div className="flex items-center justify-center min-h-[80vh]">
    <div className="text-center">
      <div className="flex items-center justify-center">
        <svg className="animate-spin w-16 h-16 text-grey2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      </div>
      <p className="mt-4 text-xl font-semibold text-grey1">Loading...</p>
      <div className="mt-4 p-2 bg-grey5 text-left text-sm text-grey2 rounded-lg shadow-inner max-w-md mx-auto">
        <pre>Please hold on for a couple of seconds...</pre>
      </div>
    </div>
  </div>
);

function App() {
  const uiLocale = useUiLocale()

  return (
    <div className="App">
      {isEducation && (
        <div className="flex justify-end px-4 py-2">
          <LocaleToggle />
        </div>
      )}
      <ScriptHostComponent
        workerUrl="./py_worker.js"
        // The Pages deployment (VITE_PLATFORM=education) has no host to hand
        // off to (ADR-0041), so it must run standalone even in a production build.
        standalone={buildEnv.DEV || isEducation}
        logLevel={buildEnv.DEV ? "debug" : "info"}
        platform={buildEnv.VITE_PLATFORM}
        defaultLocale={DEFAULT_UI_LOCALE}
        locale={devLocale ?? (isEducation ? uiLocale : undefined)}
        mapLocale={normalizeLocale}
        fallback={LoadingScreen}
        factories={[
          new DataSubmissionPageFactory({
            promptFactories: [
                new ConsentFormVizFactory(),
                new FileInputMultipleFactory(),
                new ErrorPageFactory(),
                new QuestionnaireFactory(),
                new RetryPromptFactory(),
                new IssueFormFactory(),
                new PlatformSelectionFactory(),
                new InstructionsFactory(),
            ],
          }),
        ]}
      />
    </div>
  );
}

export default App;
