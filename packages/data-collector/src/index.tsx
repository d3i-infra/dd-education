import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import { createHashRouter, RouterProvider, Navigate } from "react-router-dom";
import App from "./App";
import { LandingPage } from "./routes/landing_page";
import { About } from "./routes/about";
import { PrivacyPolicy } from "./routes/privacy_policy";
import { RouteError } from "./routes/route_error";
import "./index.css";
import "@eyra/feldspar/dist/styles.css";

const router = createHashRouter([
  { path: "/", element: <LandingPage />, errorElement: <RouteError /> },
  { path: "/about", element: <About />, errorElement: <RouteError /> },
  { path: "/privacy-policy", element: <PrivacyPolicy />, errorElement: <RouteError /> },
  { path: "/port", element: <App />, errorElement: <RouteError /> },
  { path: "*", element: <Navigate to="/" replace />, errorElement: <RouteError /> },
]);

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Failed to find the root element");
const root = ReactDOM.createRoot(rootElement);
root.render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
);
