import React from 'react';
import { Footer } from "./components/footer"
import { NavBar } from "./components/navbar"

export const About = () => {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Navigation Bar */}
      <NavBar />

      {/* About Content */}
      <main className="flex-grow container mx-auto py-8">
        <h1 className="text-3xl font-bold mb-6">About Digital Footprint Explorer</h1>
        
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">Our Mission</h2>
          <p className="text-lg text-gray-700 mb-4">
            At Digital Footprint Explorer, we're committed to helping individuals and organizations 
            understand and manage their online presence. In today's interconnected world, your digital 
            footprint can have a significant impact on your personal and professional life.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">What We Do</h2>
          <p className="text-lg text-gray-700 mb-4">
            Our cutting-edge technology analyzes your digital presence across various platforms, 
            providing valuable insights into your online activities. We offer tools and guidance to:
          </p>
          <ul className="list-disc list-inside text-lg text-gray-700 mb-4">
            <li>Assess your current digital footprint</li>
            <li>Identify potential privacy and security risks</li>
            <li>Optimize your online presence for personal or professional goals</li>
            <li>Educate users about digital citizenship and online safety</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">Our Team</h2>
          <p className="text-lg text-gray-700 mb-4">
            Digital Footprint Explorer is a collaborative project between the University of Amsterdam 
            and Utrecht University. Our team consists of researchers, data scientists, and cybersecurity 
            experts dedicated to empowering users in the digital age.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Funding</h2>
          <p className="text-lg text-gray-700 mb-4">
            This project is generously funded by PDI-SSH (Platform Digital Infrastructure - Social Sciences 
            and Humanities), supporting innovative research at the intersection of technology and society.
          </p>
        </section>
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
};

