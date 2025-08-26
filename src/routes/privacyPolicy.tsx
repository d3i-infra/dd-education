import { Footer } from "./components/footer"
import { NavBar } from "./components/navbar"

export const PrivacyPolicy = () => {
  return (
    <div class="flex flex-col min-h-screen">
      {/* Navigation Bar */}
      <NavBar />

      {/* Privacy Policy Content */}
      <main class="flex-grow container mx-auto py-8">
        <h1 class="text-3xl font-bold mb-6">Privacy Policy</h1>
        
        <section class="mb-8">
          <h2 class="text-2xl font-semibold mb-4">1. Introduction</h2>
          <p class="text-lg text-gray-700 mb-4">
            Digital Footprint Explorer is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our service.
          </p>
        </section>

        <section class="mb-8">
          <h2 class="text-2xl font-semibold mb-4">2. Information We Collect</h2>
          <p class="text-lg text-gray-700 mb-4">
            We collect <strong>no information about you</strong> in any form whatsoever. No data will be shared with anyone when using the digital footprint explorer.
          </p>
        </section>

        <section>
          <h2 class="text-2xl font-semibold mb-4">3. Your Rights</h2>
          <p class="text-lg text-gray-700 mb-4">
            If you have any questions or remarks{" "}
            <a class="underline" href="mailto:l.boeschoten@uu.nl">please contact us</a>
          </p>
        </section>
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
};

