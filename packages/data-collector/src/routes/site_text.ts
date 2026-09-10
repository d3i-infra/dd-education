import TextBundle from "@eyra/feldspar"
import { resolveAll } from "../locale/text"
import { useUiLocale } from "../locale/ui_locale"

// The site's static pages (landing, about, privacy) and the shared navbar/footer are
// participant-facing chrome, not researcher-supplied study config, so their text lives
// here as one bundle table rather than as inline JSX literals. `siteText(locale)`
// resolves the whole table at once through the fork's shared `resolveAll`, keeping the
// site consistent with how the rest of the tool resolves translated text.
//
// Dutch throughout is informal (je/jouw/jij), never u/uw — see the "no formal Dutch"
// test in static_pages.test.tsx.

const bundles = {
  siteName: new TextBundle().add("en", "Digital Footprint Explorer").add("nl", "Digitale Voetafdruk Verkenner"),
  navHome: new TextBundle().add("en", "Home").add("nl", "Home"),
  navAbout: new TextBundle().add("en", "About").add("nl", "Over"),
  heroTagline: new TextBundle().add("en", "Discover and understand your online presence").add("nl", "Ontdek en begrijp je online aanwezigheid"),
  landingIntro: new TextBundle()
    .add("en", "Welcome to Digital Footprint Explorer, a tool designed to help you analyze and explore your digital presence across various platforms. This tool can provide insights into your online activities on various platforms, helping you make informed decisions about your digital life.")
    .add("nl", "Welkom bij de Digitale Voetafdruk Verkenner, een tool waarmee je je digitale aanwezigheid op verschillende platforms kunt analyseren en verkennen. De tool geeft je inzicht in je online activiteiten, zodat je weloverwogen keuzes kunt maken over je digitale leven."),
  landingWhat: new TextBundle()
    .add("en", "The tool enables you to explore and visualize data from various platforms, helping you gain insights into your behavior and understand what these platforms collect about you. It provides instructions on how to request and download your data in the correct format. If there are any platforms missing that you'd like to see included, such as for educational purposes or data awareness please contact us. We'd be happy to add them!")
    .add("nl", "Met de tool kun je data van verschillende platforms verkennen en visualiseren, zodat je inzicht krijgt in jouw gedrag en begrijpt wat deze platforms over je verzamelen. Je krijgt uitleg over hoe je jouw data in het juiste formaat kunt opvragen en downloaden. Mis je een platform dat je graag toegevoegd zou zien, bijvoorbeeld voor educatieve doeleinden of databewustzijn, neem dan contact met ons op. We voegen het graag toe!"),
  landingCta: new TextBundle().add("en", "Click the button below to start exploring!").add("nl", "Klik op de knop hieronder om te beginnen!"),
  start: new TextBundle().add("en", "Start").add("nl", "Starten"),
  landingPartOf: new TextBundle().add("en", "The digital footprint explorer is part of").add("nl", "De Digitale Voetafdruk Verkenner is onderdeel van"),
  aboutTitle: new TextBundle().add("en", "About Digital Footprint Explorer").add("nl", "Over de Digitale Voetafdruk Verkenner"),
  aboutIntroBefore: new TextBundle()
    .add("en", "The ")
    .add("nl", "De "),
  aboutIntroStrong: new TextBundle()
    .add("en", "Digital Footprint Explorer")
    .add("nl", "Digitale Voetafdruk Verkenner"),
  aboutIntroAfter: new TextBundle()
    .add("en", " is an application that allows you to explore and reflect on the data you receive from various online platforms. By inspecting and visualizing your data, you can better understand what information platforms collect about you and how it shapes your digital presence.")
    .add("nl", " is een applicatie waarmee je de data die je van verschillende online platforms ontvangt kunt verkennen en waarop je kunt reflecteren. Door je data te bekijken en te visualiseren, begrijp je beter welke informatie platforms over je verzamelen en hoe dat je digitale aanwezigheid vormgeeft."),
  aboutDonationTitle: new TextBundle().add("en", "What Is Data Donation?").add("nl", "Wat is datadonatie?"),
  aboutDonationBody: new TextBundle()
    .add("en", "This tool uses the data donation framework Port. So what is data donation?")
    .add("nl", "Deze tool gebruikt het datadonatie-framework Port. Maar wat is datadonatie eigenlijk?"),
  aboutDonationBody2: new TextBundle()
    .add("en", "Under the EU's GDPR, you can request your personal data from online platforms known as Data Download Packages (DDPs). Data donation is a process that allows individuals like you to share only the relevant data with researchers. The donation process happens in your browser, where the tool extracts and displays your data so you can review and decide what to share. Only the data you approve will be donated for research.")
    .add("nl", "Onder de AVG van de EU kun je je persoonsgegevens opvragen bij online platforms; deze staan bekend als Data Download Packages (DDP's). Datadonatie is een proces waarmee mensen zoals jij alleen de relevante data met onderzoekers kunnen delen. Het donatieproces vindt plaats in je browser, waar de tool jouw data uitleest en toont zodat je kunt bekijken en beslissen wat je wilt delen. Alleen de data die jij goedkeurt, wordt gedoneerd voor onderzoek."),
  aboutHowTitle: new TextBundle().add("en", "How Does This App Work?").add("nl", "Hoe werkt deze app?"),
  aboutHowBody: new TextBundle()
    .add("en", "This application uses the tool ")
    .add("nl", "Deze applicatie gebruikt de tool "),
  aboutHowBodyStrong: new TextBundle().add("en", "Port").add("nl", "Port"),
  aboutHowBodyAfter: new TextBundle()
    .add("en", ", designed to guide you through the data donation workflow entirely in your browser. It helps you extract, explore, and review your data before choosing whether to donate it, ensuring you remain in full control at every step.")
    .add("nl", ", die is ontworpen om je volledig in je browser door het datadonatieproces te begeleiden. De tool helpt je jouw data uit te lezen, te verkennen en te bekijken voordat je beslist of je die doneert, zodat je bij elke stap zelf de controle houdt."),
  aboutHowBody2: new TextBundle()
    .add("en", "This app uses parts of the Port software. By default, your data stays in your browser and is not shared with anyone. If you encounter an issue, you may optionally send an anonymous report to help us improve the tool.")
    .add("nl", "Deze app gebruikt onderdelen van de Port-software. Standaard blijft jouw data in je browser en wordt die met niemand gedeeld. Loop je tegen een probleem aan, dan kun je optioneel een anoniem rapport versturen om ons te helpen de tool te verbeteren."),
  aboutProjectTitle: new TextBundle().add("en", "The Project").add("nl", "Het project"),
  aboutProjectBefore: new TextBundle()
    .add("en", "The Digital Footprint Explorer is developed as part of the")
    .add("nl", "De Digitale Voetafdruk Verkenner is ontwikkeld als onderdeel van het"),
  aboutProjectLink: new TextBundle().add("en", "Data Donation Project").add("nl", "Data Donation Project"),
  aboutProjectAfter: new TextBundle()
    .add("en", ". This project builds the Data Donation Infrastructure (D3I), which enables researchers to conduct ethical and transparent data donation studies. It is a collaboration between universities including the University of Amsterdam and Utrecht University, and is funded by PDI-SSH.")
    .add("nl", ". Dit project bouwt aan de Data Donation Infrastructure (D3I), waarmee onderzoekers ethische en transparante datadonatiestudies kunnen uitvoeren. Het is een samenwerking tussen universiteiten, waaronder de Universiteit van Amsterdam en de Universiteit Utrecht, en wordt gefinancierd door PDI-SSH."),
  privacyTitle: new TextBundle().add("en", "Privacy Policy").add("nl", "Privacybeleid"),
  privacyIntroTitle: new TextBundle().add("en", "1. Introduction").add("nl", "1. Inleiding"),
  privacyIntroBody: new TextBundle()
    .add("en", "Digital Footprint Explorer is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our service.")
    .add("nl", "Digitale Voetafdruk Verkenner zet zich in om jouw privacy te beschermen. Dit privacybeleid legt uit hoe we jouw informatie verzamelen, gebruiken, delen en beveiligen wanneer je onze dienst gebruikt."),
  privacyCollectTitle: new TextBundle().add("en", "2. Information We Collect").add("nl", "2. Welke gegevens we verzamelen"),
  privacyCollectBefore: new TextBundle()
    .add("en", "By default, all data processing happens locally in your browser and ")
    .add("nl", "Standaard vindt alle gegevensverwerking lokaal in je browser plaats en "),
  privacyCollectStrong: new TextBundle()
    .add("en", "no data is collected or shared")
    .add("nl", "wordt er geen data verzameld of gedeeld"),
  privacyCollectAfter: new TextBundle()
    .add("en", ". If you encounter an issue with the data extraction, you may optionally send an anonymous report containing only the file structure of your data package (not its contents) to help us improve the tool.")
    .add("nl", ". Loop je tegen een probleem aan bij het uitlezen van je data, dan kun je optioneel een anoniem rapport versturen met alleen de bestandsstructuur van je datapakket (niet de inhoud ervan) om ons te helpen de tool te verbeteren."),
  privacyRightsTitle: new TextBundle().add("en", "3. Your Rights").add("nl", "3. Je rechten"),
  privacyRightsBody: new TextBundle().add("en", "If you have any questions or remarks").add("nl", "Heb je vragen of opmerkingen,"),
  privacyContact: new TextBundle().add("en", "please contact us").add("nl", "neem dan contact met ons op"),
  // The footer mirrors datadonation.eu and stays in English in both locales
  // (Danielle, Task 4 review): the nl values repeat the en text on purpose.
  footerPrivacy: new TextBundle().add("en", "Privacy Policy").add("nl", "Privacy Policy"),
  footerProvidedBy: new TextBundle().add("en", "A service provided by").add("nl", "A service provided by"),
  footerSupportedBy: new TextBundle().add("en", "and supported by").add("nl", "and supported by"),
  footerPartners: new TextBundle().add("en", "Project partners").add("nl", "Project partners"),
  landingHeroAlt: new TextBundle().add("en", "Digital Footprint Banner").add("nl", "Banner Digitale Voetafdruk"),
  languageGroup: new TextBundle().add("en", "Language").add("nl", "Taal"),
}

export function siteText (locale: string): Record<string, string> {
  return resolveAll(bundles, locale)
}

export function useSiteText (): Record<string, string> {
  return siteText(useUiLocale())
}
