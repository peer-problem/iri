import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import LandingPage from "./LandingPage";
import "./styles.css";
import "./landing.css";

const path = window.location.pathname.replace(/\/+$/, "") || "/";
const page = path === "/chat" ? <App /> : <LandingPage />;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {page}
  </StrictMode>,
);
