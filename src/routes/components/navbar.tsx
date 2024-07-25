import React from 'react';
import { Link } from "react-router-dom";

export const NavBar = () => {
  return (
  <nav className="bg-gray-200 text-black p-4">
    <div className="container mx-auto flex justify-between items-center">
      <div className="text-xl font-bold">Digital Footprint Explorer</div>
      <ul className="flex space-x-4">
        <li><Link to="/" className="hover:text-gray-300">Home</Link></li>
        <li><Link to="/about" className="hover:text-gray-300">About</Link></li>
      </ul>
    </div>
  </nav>
  );
};
