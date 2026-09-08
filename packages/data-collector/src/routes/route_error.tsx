import { useRouteError, Link } from "react-router-dom";
import { readUiLocale } from "../locale/ui_locale";

// A route-level fallback: without an `errorElement`, a render fault surfaces
// react-router's own "Unexpected Application Error" page, stack trace and
// all. This shows a short, translated message instead, plus whatever the
// thrown error's `.message` was (never the stack) and a way back into the
// tool.

interface RouteErrorTexts {
  heading: string;
  backLink: string;
}

const TEXTS: Record<"en" | "nl", RouteErrorTexts> = {
  en: {
    heading: "Something went wrong while showing this page.",
    backLink: "Back to the platforms",
  },
  nl: {
    heading: "Er ging iets mis bij het tonen van deze pagina.",
    backLink: "Terug naar de platforms",
  },
};

function getTexts(): RouteErrorTexts {
  return readUiLocale() === "nl" ? TEXTS.nl : TEXTS.en;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "object" && error !== null && "message" in error) {
    const message = (error as { message: unknown }).message;
    if (typeof message === "string") return message;
  }
  return String(error);
}

export const RouteError = () => {
  const error = useRouteError();
  const texts = getTexts();

  return (
    <div className="flex flex-col min-h-screen items-center justify-center px-4 py-8 text-center">
      <p className="text-lg text-grey1 mb-4">{texts.heading}</p>
      <pre className="text-sm text-grey1 bg-grey5 rounded-md p-4 mb-6 max-w-full overflow-auto whitespace-pre-wrap">
        {errorMessage(error)}
      </pre>
      <Link to="/port" className="text-primary hover:underline font-medium">
        {texts.backLink}
      </Link>
    </div>
  );
};
