import React from 'react';
import { Link } from "react-router-dom";

export const NavBar = () => {
  return (
  <nav class="bg-gray-200 text-black p-4">
    <div class="container mx-auto flex justify-between items-center">
      <div class="text-xl font-bold">Digital Footprint Explorer</div>
      <ul class="flex space-x-4">
        <li><Link to="/" class="hover:text-gray-300">Home</Link></li>
        <li><Link to="/about" class="hover:text-gray-300">About</Link></li>
      </ul>
    </div>
  </nav>
  );
};
