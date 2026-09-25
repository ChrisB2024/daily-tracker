// Service worker for the installable app (Build Plan 3, Units 22–23).
//
// Deliberately does no caching and has no fetch handler: every request goes
// to the network as before, so a deploy can never be hidden behind a stale
// cached copy. It exists because iOS delivers web push only to an installed
// app with a service worker.

self.addEventListener("install", () => {
  // Take over as soon as a new version is installed, rather than waiting for
  // every open tab to close.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// A push from services/push.py: {"title", "body", "url"}.
self.addEventListener("push", (event) => {
  let data;
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Daily Tracker", {
      body: data.body || "",
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      data: { url: data.url || "/" },
    }),
  );
});

// Tapping a notification focuses the open app (navigating it to the url), or
// opens it if it is closed.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url || "/", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if ("focus" in client) {
          return client.navigate(url).then((c) => (c || client).focus());
        }
      }
      return self.clients.openWindow(url);
    }),
  );
});
