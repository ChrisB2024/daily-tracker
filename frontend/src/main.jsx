import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/dashboard.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Installable app (Unit 22): iOS only delivers web push to a home-screen app
// with a service worker. Registration failing is harmless — the app works the
// same without it.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
