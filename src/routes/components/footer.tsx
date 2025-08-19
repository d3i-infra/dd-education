import { Link } from "react-router-dom";
import pdiSshLogo from "../icons/pdi_ssh_logo.png"
import uvaLogo from "../icons/uva_logo.png"
import uuLogo from "../icons/uu_logo.png"

export const Footer = () => {
  return (
  <footer class="bg-gray-200 py-6">
  <div class="container mx-auto flex flex-wrap justify-between items-center">
    <div class="text-sm text-gray-600 mb-2 md:mb-0">
      © 2025 Digital Footprint Explorer. All rights reserved.
      <span class="mx-2">|</span>
      <Link to="/privacy-policy" class="hover:text-gray-900 underline">Privacy Policy</Link>
    </div>
    <div class="flex items-center space-x-4">
      <span class="text-sm text-gray-600">Funded by PDI-SSH</span>
      <img src={pdiSshLogo} alt="PDI-SSH" class="h-34 w-34 object-contain" />
      <img src={uvaLogo} alt="University of Amsterdam" class="h-34 w-34 object-contain" />
      <img src={uuLogo} alt="Utrecht University" class="h-34 w-34 object-contain" />
    </div>
  </div>
</footer>
  );
};
