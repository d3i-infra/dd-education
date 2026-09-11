import { Link } from "react-router-dom";
import { useSiteText } from "../site_text";
import odissei from "../icons/partners/odissei.png";
import eyra from "../icons/partners/eyra.png";
import uva from "../icons/partners/uva.png";
import ru from "../icons/partners/ru.png";
import uu from "../icons/partners/uu.png";
import vu from "../icons/partners/vu.png";
import tilburg from "../icons/partners/tilburg.svg";
import eur from "../icons/partners/eur.png";

const PARTNERS: Array<{ src: string; alt: string; className: string }> = [
  { src: uva, alt: "University of Amsterdam", className: "max-h-5" },
  { src: ru, alt: "Radboud University", className: "max-h-6" },
  { src: uu, alt: "Utrecht University", className: "max-h-8" },
  { src: vu, alt: "Vrije Universiteit Amsterdam", className: "max-h-6" },
  { src: tilburg, alt: "Tilburg University", className: "max-h-6" },
  { src: eur, alt: "Erasmus University Rotterdam", className: "max-h-10" },
];

export const Footer = () => {
  const text = useSiteText();

  return (
    <footer className="border-t border-grey4 bg-white py-6 px-4 text-sm text-grey2">
      <div className="mx-auto max-w-[72rem] flex flex-col gap-4">
        <p className="flex flex-wrap items-center gap-2 border-b border-grey4 pb-3">
          <span>{text.footerProvidedBy}</span>
          <img src={odissei} alt="ODISSEI" className="h-6 max-h-6 object-contain" />
          <span>{text.footerSupportedBy}</span>
          <img src={eyra} alt="Eyra" className="h-6 max-h-6 object-contain" />
        </p>
        <div className="flex flex-col gap-2">
          <p>{text.footerPartners}</p>
          <div className="flex flex-wrap items-center gap-x-7 gap-y-3">
            {PARTNERS.map((p) => (
              <img key={p.alt} src={p.src} alt={p.alt} className={`object-contain ${p.className}`} />
            ))}
          </div>
        </div>
        <p className="flex flex-wrap items-center gap-2">
          <span>© {new Date().getFullYear()} datadonation.eu</span>
          <span aria-hidden="true">·</span>
          <Link to="/privacy-policy" className="underline hover:text-grey1">{text.footerPrivacy}</Link>
        </p>
      </div>
    </footer>
  );
};
