# Build Plan 3 — Goal links and push notifications

Decided 2026-09-24, after Build Plan 2 (the calendar-first redesign) shipped.
These are the two items that plan left under "Not units yet". Units continue
from 21, land in order, and each is verified before the next starts.

## Decisions (Chris, 2026-09-24)

| Question | Answer |
| -------- | ------ |
| What do lines between goals mean? | **Worked the same day.** In the week graph, two goals are linked when both had a completed task on the same day; the more shared days, the stronger the line. |
| What should push notifications say? | **All three:** an evening check-off reminder, a morning plan summary, and a weekly recap. |
| Which device receives them? | **iPhone.** Web push on iOS only works for a site added to the Home Screen (iOS 16.4+), so the tracker must become an installable web app first. |

Defaults chosen by the agent, not yet confirmed — change freely:

| Setting | Default |
| ------- | ------- |
| Evening reminder | 21:00 `settings.tz`, **only if** today has pending tasks: "4 tasks still unchecked today" |
| Morning summary | 08:00: "Today: 5 tasks · Hitwin, Angle, …" or "Nothing on the calendar today" |
| Weekly recap | Sunday 20:00: the week's goal ranking by minutes completed. No AI, no audio — the retired debrief stays retired. |
| "Worked on a goal" | At least one **completed** task that day. Missed and pending don't count. |
| Goal links in the day view | None: every goal in a day graph was worked that day, so a link would say nothing. |

## Units

### Unit 21 — Goal links in the week graph — shipped 2026-09-24

**Builds:** `get_task_graph` adds goal→goal links for every pair of goals that
both had a completed task on the same day in the range, with `weight` = number
of shared days. Only for ranges longer than one day. Links carry
`kind: "shared_day"`; the existing task→goal links get `kind: "task"`. The week
graph draws shared-day links fainter than task links, and thicker with weight.
**Done when:** two goals completed on the same two days are linked with weight
2 · a goal with only missed tasks that day is not linked · the day graph has no
goal→goal links · hovering a link says "worked the same day on N days".

### Unit 22 — Installable web app

**Builds:** `manifest.webmanifest`, icons (192, 512, and a 180px
`apple-touch-icon`), the iOS meta tags, and a service worker registered from
`main.jsx`. The service worker does nothing yet except exist — no offline
caching, so a deploy is never masked by a stale cache.
**Done when:** Safari on iPhone offers "Add to Home Screen", the icon appears,
and the app opens full-screen from it.

### Unit 23 — Push plumbing

**Builds:** `pywebpush` dependency; a `push_subscriptions` table (endpoint,
keys, created_at — additive migration); `GET /push/public-key`,
`POST /push/subscribe`, `DELETE /push/subscribe`, `POST /push/test`;
`services/push.py` that sends to every stored subscription and deletes ones the
push service reports gone (404/410). Service worker gains `push` and
`notificationclick` handlers. A "Notifications" control on Goals: enable,
disable, send a test — with the Add-to-Home-Screen instruction shown instead
when opened in a normal Safari tab.

**Needs Chris:** two Railway variables, `VAPID_PUBLIC_KEY` and
`VAPID_PRIVATE_KEY` (plus `VAPID_SUBJECT`, a `mailto:`). Generated once; the
private key never leaves Railway. Without them the endpoints answer 503 and
the control says push is not configured.

**Storage note (S2):** a push subscription lets its holder *address* the phone
but not *send* to it — sending needs the VAPID private key, which lives only in
the environment. So storing subscriptions in the unauthenticated database is
acceptable under S2; `architecture.md` records it when this lands.

**Done when:** "Send test" on the installed iPhone app produces a notification
· disabling removes the subscription · an expired subscription is deleted on
the next send.

### Unit 24 — The three notifications

**Builds:** three scheduler jobs in `settings.tz` using `services/push.py`:
evening reminder, morning summary, weekly recap, with the defaults above.
Message text built by pure functions (tested directly). Tapping a notification
opens Today (reminder, summary) or the week graph (recap). Registered only when
VAPID is configured.
**Done when:** each job, run by hand against seeded data, sends the expected
text · the evening reminder sends nothing when every task is done · startup
logs the next fire time of each.

## Open questions

- Should notification times be editable in the app, or are fixed times fine?
  Fixed until asked.
