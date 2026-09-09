import { Footer } from "./components/footer";
import { NavBar } from "./components/navbar";
import { useSiteText } from "./site_text";
import { useUiLocale } from "../locale/ui_locale";

export const About = () => {
  const text = useSiteText();
  const locale = useUiLocale();

  return (
    <div className="flex flex-col min-h-screen">
      <NavBar />

      <main lang={locale} className="flex-grow container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-6">{text.aboutTitle}</h1>

        <section className="mb-8">
          <p className="text-lg text-grey1 mb-4">
            {text.aboutIntroBefore}<strong>{text.aboutIntroStrong}</strong>{text.aboutIntroAfter}
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">{text.aboutDonationTitle}</h2>
          <p className="text-lg text-grey1 mb-4">
            {text.aboutDonationBody}
            <br />
            <br />
            {text.aboutDonationBody2}
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">{text.aboutHowTitle}</h2>
          <p className="text-lg text-grey1 mb-4">
            {text.aboutHowBody}<strong>{text.aboutHowBodyStrong}</strong>{text.aboutHowBodyAfter}
            <br />
            <br />
            {text.aboutHowBody2}
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">{text.aboutProjectTitle}</h2>
          <p className="text-lg text-grey1 mb-4">
            {text.aboutProjectBefore}{" "}
            <a href="https://datadonation.eu" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">{text.aboutProjectLink}</a>
            {text.aboutProjectAfter}
          </p>
        </section>
      </main>

      <Footer />
    </div>
  );
};
