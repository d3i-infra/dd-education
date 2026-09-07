import { Link, useLocation } from "react-router-dom";

export const NavBar = () => {
  const location = useLocation();

  const getLinkClasses = (path: string) => {
    const baseClasses = "px-3 py-2 rounded-md transition-colors duration-200";
    const isActive = location.pathname === path;

    if (isActive) {
      return `${baseClasses} bg-primary text-white font-medium`;
    }
    return `${baseClasses} hover:bg-primarylight hover:text-primary`;
  };

  return (
    <nav className="bg-grey5 text-black p-4 shadow-md">
      <div className="container mx-auto px-4 flex justify-between items-center">
        <div className="text-xl font-bold text-grey1">Digital Footprint Explorer</div>
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
