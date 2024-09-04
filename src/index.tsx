import * as React from "react";
import * as ReactDOM from "react-dom/client";
import {
  createHashRouter,
  createBrowserRouter,
  RouterProvider,
} from "react-router-dom";

import './fonts.css'
import './framework/styles.css'
import Port from "./routes/port"
import { LandingPage } from "./routes/landingPage"
import { About } from "./routes/about"
import { PrivacyPolicy } from "./routes/privacyPolicy"


const rootElement = document.getElementById('root') as HTMLElement
const root =  ReactDOM.createRoot(rootElement)

const router = createHashRouter([
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
    element: <Port root={root} locale="en"/>
  },
],
);


root.render(
  <RouterProvider router={router} />
);


