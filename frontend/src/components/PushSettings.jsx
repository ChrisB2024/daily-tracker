import { useEffect, useState } from "react";
import {
  deletePushSubscription,
  getPushConfig,
  savePushSubscription,
  sendTestPush,
} from "../api";

// Notifications on/off for this device (Build Plan 3, Unit 23). Lives on the
// Goals page. On iPhone, web push only works from the Home Screen app, so a
// normal Safari tab gets the install steps instead of a button.

// The VAPID public key arrives base64url-encoded; PushManager wants bytes.
function urlBase64ToUint8Array(base64) {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}

function detectSupport() {
  const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
  const standalone =
    window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  if (isIOS && !standalone) return "needs-install";
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return "unsupported";
  return "supported";
}

async function loadState() {
  const config = await getPushConfig();
  const support = detectSupport();
  let subscription = null;
  if (config.enabled && support === "supported") {
    const reg = await navigator.serviceWorker.ready;
    subscription = await reg.pushManager.getSubscription();
  }
  return { config, support, subscribed: Boolean(subscription) };
}

export default function PushSettings() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);

  useEffect(() => {
    loadState()
      .then(setState)
      .catch((err) => setError(err.message));
  }, []);

  async function run(action) {
    setBusy(true);
    setNote(null);
    try {
      await action();
      setState(await loadState());
    } catch (err) {
      alert("Failed: " + err.message);
    } finally {
      setBusy(false);
    }
  }

  function enable() {
    return run(async () => {
      // Must be called from the tap itself — iOS refuses a prompt that is not
      // the direct result of a user gesture.
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        throw new Error("notifications are blocked — allow them in Settings → Notifications");
      }
      const reg = await navigator.serviceWorker.ready;
      const subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(state.config.public_key),
      });
      await savePushSubscription(subscription.toJSON());
    });
  }

  function disable() {
    return run(async () => {
      const reg = await navigator.serviceWorker.ready;
      const subscription = await reg.pushManager.getSubscription();
      if (subscription) {
        await deletePushSubscription(subscription.endpoint);
        await subscription.unsubscribe();
      }
    });
  }

  function test() {
    return run(async () => {
      const { sent } = await sendTestPush();
      setNote(sent > 0 ? "Test sent — it should arrive in a few seconds." : "No device is subscribed.");
    });
  }

  let body;
  if (error) {
    body = <div className="error">Error: {error}</div>;
  } else if (!state) {
    body = <div className="loading">Loading…</div>;
  } else if (!state.config.enabled) {
    body = <p className="push-note">Push isn't set up on the server yet.</p>;
  } else if (state.support === "needs-install") {
    body = (
      <p className="push-note">
        On iPhone, notifications only work from the Home Screen app: tap Share →
        Add to Home Screen, then open Tracker from its icon and come back here.
      </p>
    );
  } else if (state.support === "unsupported") {
    body = <p className="push-note">This browser can't receive push notifications.</p>;
  } else {
    body = (
      <div className="push-controls">
        <span className="push-status">{state.subscribed ? "On for this device" : "Off"}</span>
        {state.subscribed ? (
          <>
            <button className="btn-secondary" onClick={test} disabled={busy}>
              Send test
            </button>
            <button className="btn-secondary" onClick={disable} disabled={busy}>
              Turn off
            </button>
          </>
        ) : (
          <button className="btn-primary" onClick={enable} disabled={busy}>
            Turn on notifications
          </button>
        )}
        {note && <span className="push-note">{note}</span>}
      </div>
    );
  }

  return (
    <section className="push-settings">
      <h3>Notifications</h3>
      {body}
    </section>
  );
}
