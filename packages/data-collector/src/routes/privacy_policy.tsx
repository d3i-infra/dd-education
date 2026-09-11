import { Footer } from "./components/footer";
import { NavBar } from "./components/navbar";
import { useSiteText } from "./site_text";
import { useUiLocale } from "../locale/ui_locale";

export const PrivacyPolicy = () => {
  const text = useSiteText();
  const locale = useUiLocale();

  return (
    <div className="flex flex-col min-h-screen">
      {/* Navigation Bar */}
      <NavBar />

      {/* Privacy Policy Content */}
      <main lang={locale} className="flex-grow container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-6">{text.privacyTitle}</h1>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">{text.privacyIntroTitle}</h2>
          <p className="text-lg text-grey1 mb-4">
            {text.privacyIntroBody}
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">{text.privacyCollectTitle}</h2>
          <p className="text-lg text-grey1 mb-4">
            {text.privacyCollectBefore}<strong>{text.privacyCollectStrong}</strong>{text.privacyCollectAfter}
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">{text.privacyRightsTitle}</h2>
          <p className="text-lg text-grey1 mb-4">
            {text.privacyRightsBody}{" "}
            <a className="underline" href="mailto:l.boeschoten@uu.nl">{text.privacyContact}</a>
          </p>
        </section>
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
};
