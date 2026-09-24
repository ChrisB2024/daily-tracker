// Service worker for the installable app (Unit 22 of Build Plan 3).
//
// Deliberately does no caching and has no fetch handler: every request goes
// to the network as before, so a deploy can never be hidden behind a stale
// cached copy. It exists because iOS delivers web push only to an installed
// app with a service worker. The push handlers arrive in Unit 23.

self.addEventListener("install", () => {
  // Take over as soon as a new version is installed, rather than waiting for
  // every open tab to close.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});
