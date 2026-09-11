import { PrimaryButton } from "@eyra/feldspar";
import { useNavigate } from "react-router-dom";
import { Footer } from "./components/footer";
import { NavBar } from "./components/navbar";
import hero from "./icons/hero.svg";
import { useSiteText } from "./site_text";
import { useUiLocale } from "../locale/ui_locale";

export const LandingPage = () => {
  const navigate = useNavigate();
  const to = "/port";
  const text = useSiteText();
  const locale = useUiLocale();

  const handleClick = () => {
    navigate(to);
  };

  return (
    <div className="flex flex-col min-h-screen">
      <NavBar />

      {/* Hero Section with Left Banner Image and Right Text */}
      <header className="bg-primary h-96">
        <div className="container mx-auto px-4 h-full flex">
          {/* Left side - Banner Image */}
          <div className="w-1/2 h-full flex items-center justify-center overflow-hidden">
            <img
              src={hero}
              alt={text.landingHeroAlt}
              className="max-w-full max-h-full object-contain"
            />
          </div>
          {/* Right side - Text Content */}
          <div className="w-1/2 flex flex-col justify-center items-center p-8">
            <h1 className="text-4xl text-white font-bold mb-4 text-center">{text.siteName}</h1>
            <p className="text-xl text-white text-center">{text.heroTagline}</p>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main lang={locale} className="flex-grow container mx-auto px-4 py-8">
        <p className="text-lg mb-3 text-grey1">
          {text.landingIntro}
        </p>
        <p className="text-lg mb-3 text-grey1">
          {text.landingWhat}
        </p>
        <p className="text-lg mb-3 text-grey1">
          {text.landingCta}
        </p>

        <div className="flex flex-row gap-4 mt-4 mb-4">
          <PrimaryButton
            label={text.start}
            onClick={handleClick}
            color="bg-success text-white"
            spinning={false}
          />
        </div>

        <p className="text-lg mb-3 text-grey1">
          {text.landingPartOf}{" "}
          <a
            href="https://datadonation.eu"
            className="text-primary hover:text-primary hover:underline font-medium transition-colors duration-200"
            target="_blank"
            rel="noopener noreferrer"
          >
            datadonation.eu
          </a>
        </p>
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
};
