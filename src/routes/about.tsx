import React from 'react';
import { Footer } from "./components/footer";
import { NavBar } from "./components/navbar";

export const About = () => {
  return (
    <div class="flex flex-col min-h-screen">
      <NavBar />

      <main class="flex-grow container mx-auto py-8">
        <h1 class="text-3xl font-bold mb-6">About Digital Footprint Explorer</h1>

        <section class="mb-8">
          <p class="text-lg text-gray-700 mb-4">
            The <strong>Digital Footprint Explorer</strong> is an application that allows you 
            to explore and reflect on the data you receive from various online platforms. 
            By inspecting and visualizing your data, you can better understand what information 
            platforms collect about you and how it shapes your digital presence. 
          </p>
        </section>

        <section class="mb-8">
          <h2 class="text-2xl font-semibold mb-4">What Is Data Donation?</h2>
          <p class="text-lg text-gray-700 mb-4">
            This tool uses the data donation framework Port. So what is data donation?
            <br></br>
            <br></br>
            Under the EU’s GDPR, you can request your personal data from online platforms
            known as Data Download Packages (DDPs). Data donation is a process that allows 
            individuals like you to share only the relevant data with researchers. The 
            donation process happens in your browser, where the tool extracts and displays 
            your data so you can review and decide what to share. Only the data you approve 
            will be donated for research.
          </p>
        </section>

        <section class="mb-8">
          <h2 class="text-2xl font-semibold mb-4">How Does This App Work?</h2>
          <p class="text-lg text-gray-700 mb-4">
            This application uses the tool <strong>Port</strong>, designed to guide you 
            through the data donation workflow entirely in your browser. It helps you extract, 
            explore, and review your data before choosing whether to donate it, ensuring you 
            remain in full control at every step.
            <br></br>
            <br></br>
            This app uses parts of the Port software, however all data remains private to you. Thus, when using the digital footprint explorer <strong>no data will be shared with anyone</strong>.

          </p>
        </section>

        <section class="mb-8">
          <h2 class="text-2xl font-semibold mb-4">The Project</h2>
          <p class="text-lg text-gray-700 mb-4">
            The Digital Footprint Explorer is developed as part of the 
            <a href="https://datadonation.eu" class="text-blue-600 hover:underline"> Data Donation Project</a>. 
            This project builds Europe’s Data Donation Infrastructure (D3I), which enables 
            researchers to conduct ethical and transparent data donation studies. It is a 
            collaboration between universities including the University of Amsterdam and 
            Utrecht University, and is funded by PDI-SSH.
          </p>
        </section>

      </main>

      <Footer />
    </div>
  );
};

