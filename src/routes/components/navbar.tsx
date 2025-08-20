import React from 'react';
import { Link, useLocation } from "react-router-dom";

export const NavBar = () => {
  const location = useLocation();
  
  const getLinkClasses = (path) => {
    const baseClasses = "px-3 py-2 rounded-md transition-colors duration-200";
    const isActive = location.pathname === path;
    
    if (isActive) {
      return `${baseClasses} bg-blue-500 text-white font-medium`;
    }
    return `${baseClasses} hover:bg-blue-100 hover:text-blue-700`;
  };

  return (
    <nav className="bg-gray-200 text-black p-4 shadow-md">
      <div className="container mx-auto flex justify-between items-center">
        <div className="text-xl font-bold text-gray-800">Digital Footprint Explorer</div>
        <ul className="flex space-x-2">
          <li>
            <Link to="/" className={getLinkClasses("/")}>
              Home
            </Link>
          </li>
          <li>
            <Link to="/about" className={getLinkClasses("/about")}>
              About
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  );
};
