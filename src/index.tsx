import * as React from "react";
import * as ReactDOM from "react-dom/client";
import {
  createBrowserRouter,
  RouterProvider,
} from "react-router-dom";

import './fonts.css'
import './framework/styles.css'
import ReactEngineComponent from "./routes/port"
import { LandingPage } from "./routes/landingPage"
import { About } from "./routes/about"
import { PrivacyPolicy } from "./routes/privacyPolicy"


const rootElement = document.getElementById('root') as HTMLElement
const root =  ReactDOM.createRoot(rootElement)

const router = createBrowserRouter([
  {
    path: "/",
    element: <LandingPage />
  },
  {
    path: "/about",
    element: <About />
  },
  {
    path: "/privacy-policy",
    element: <PrivacyPolicy />
  },
  {
    path: "/port",
    element: <ReactEngineComponent root={root} locale="en"/>
  },
]);


root.render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);


