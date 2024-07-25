import React from 'react';

export const NavBar = () => {
  return (
  <nav className="bg-gray-200 text-black p-4">
    <div className="container mx-auto flex justify-between items-center">
      <div className="text-xl font-bold">Digital Footprint Explorer</div>
      <ul className="flex space-x-4">
        <li><a href="/" className="hover:text-gray-300">Home</a></li>
        <li><a href="/about" className="hover:text-gray-300">About</a></li>
      </ul>
    </div>
  </nav>
  );
};
