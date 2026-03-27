import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import { createHashRouter, RouterProvider, Navigate } from "react-router-dom";
import App from "./App";
import { LandingPage } from "./routes/landing_page";
import { About } from "./routes/about";
import { PrivacyPolicy } from "./routes/privacy_policy";
import "./index.css";
import "@eyra/feldspar/dist/styles.css";

const router = createHashRouter([
  { path: "/", element: <LandingPage /> },
  { path: "/about", element: <About /> },
  { path: "/privacy-policy", element: <PrivacyPolicy /> },
  { path: "/port", element: <App /> },
  { path: "*", element: <Navigate to="/" replace /> },
]);

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Failed to find the root element");
const root = ReactDOM.createRoot(rootElement);
root.render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
);
