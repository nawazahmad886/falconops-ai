import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import * as serviceWorkerRegistration from "@/serviceWorkerRegistration";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// See serviceWorkerRegistration.js / public/service-worker.js — never caches
// /api/* (live monitoring data), only enables installability + static-asset caching.
serviceWorkerRegistration.register();
