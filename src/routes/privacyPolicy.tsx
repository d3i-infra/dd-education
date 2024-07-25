import React from 'react';
import { Footer } from "./components/footer"
import { NavBar } from "./components/navbar"

export const PrivacyPolicy = () => {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Navigation Bar */}
      <NavBar />

      {/* Privacy Policy Content */}
      <main className="flex-grow container mx-auto py-8">
        <h1 className="text-3xl font-bold mb-6">Privacy Policy</h1>
        
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">1. Introduction</h2>
          <p className="text-lg text-gray-700 mb-4">
            Digital Footprint Explorer is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our service.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">2. Information We Collect</h2>
          <p className="text-lg text-gray-700 mb-4">
            We collect no information about you in any form whatsoever
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">3. Your Rights</h2>
          <p className="text-lg text-gray-700 mb-4">
            If you have any questions or remarks please contact: email@email.com
          </p>
        </section>
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
};

