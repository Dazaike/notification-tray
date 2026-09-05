import React from "react";
import ReactDOM from "react-dom/client";
import { Overlay } from "./surfaces/Overlay";
import { Center } from "./surfaces/Center";
import { Panel } from "./surfaces/Panel";
import "./index.css";

function App() {
  const surface = new URLSearchParams(window.location.search).get("surface") || "overlay";

  switch (surface) {
    case "center":
      return <Center />;
    case "panel":
      return <Panel />;
    case "overlay":
    default:
      return <Overlay />;
  }
}

const rootElement = document.getElementById("root");
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
