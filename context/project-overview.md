# Daily Tracker

Recovered from the codebase and `readme.md` on 2026-09-03. Scope and status
confirmed by Chris; everything else is observed from code.

## The Problem

> Chris currently re-derives "did I actually move the needle this week?" from
> memory and a scattered Google Calendar because habit trackers score inputs and
> task managers score noise, and this eliminates it by making every unit of work
> a binary rep tagged to a goal, mirroring its status into the calendar he
> already checks, and reporting the gap between committed and completed in a
> Sunday debrief built from rep data instead of self-report.

## Who Hurts

- **Primary user:** Chris — sole user, sole operator. Founder running multiple
  products (Hitwin, Argos, and the goals tracked in this system), responsible
  for his own throughput with nobody assigning work.
- **What he did before:** goals in his head, work in a calendar with no
  completion state, progress assessed by feel on Sunday night.
- **What it cost:** no evidence trail. Avoidance was invisible — a rep type
  skipped three weeks running looked the same as one hit every day, because
  nothing counted either. Weeks felt productive or unproductive with no number
  attached.

## What This Is

A single-user goal-driven rep tracker. Goals contain user-defined **rep types**
(a named binary unit of work with a one-line done/not-done criterion). Rep types
are scheduled as **reps** on specific dates and times. Each rep writes a Google
Calendar event that starts gray, turns green when checked off, and red when
missed — so the calendar Chris already opens becomes the scoreboard. The backend
computes chains, daily score, weekly total and weekly PR at read time, and a
Sunday job emails a Claude-generated debrief with an ElevenLabs MP3 attached.

## Causality Chain

The debrief quantifies avoidance he would otherwise rationalize → he confronts
the specific rep that isn't happening → the goals those reps ladder to actually
ship → the products those goals belong to make money. There is no retention
metric here; the only user is the operator, and the product dies the moment he
stops opening it.

## Core Flow

1. Open the **Goals** view, create a goal (title, optional description, optional target date).
2. Expand that goal, add 3–5 rep types — each needs a name, a one-line criterion, and a duration. Optionally a daily floor, a weekly target, an emoji, and the first-rep flag.
3. Open the **Schedule** view, pick the goal, pick a rep type, pick a date and time. Optionally check "recurring" to fan it out over the next N days.
4. Each created rep POSTs to `/reps` (or `/reps/bulk`), which inserts the row and then inserts a gray (`colorId: 8`) Google Calendar event titled `[<RepType>] <Goal title>`, storing the returned event id on the rep.
5. Next morning, open **Today**. See daily score, week total, weekly PR, first-rep-before-noon rate, the month heatmap, and today's reps grouped by goal.
6. Do the work, press the ○ on the rep. Status goes `completed`, `completed_at` is stamped in `settings.tz`, and the calendar event patches to green (`colorId: 10`).
7. Unfinished reps are swept to `missed` and patched red (`colorId: 11`) — currently only by pressing **Run end-of-day sweep** on the dashboard, because no automatic 23:59 job exists.
8. Sunday, the scheduled job aggregates the week, sends it to Claude, converts the text to MP3 via ElevenLabs, and emails both to Chris's own Gmail address.
9. **Debrief** view regenerates the same summary on demand and plays or downloads the audio.

## Capabilities

### Goals and rep types
- Create, list, read, patch goals. Duplicate titles rejected with 409.
- Delete a goal: soft by default (`status = archived`), or `?hard=true` to purge its rep types and reps permanently.
- Create and list rep types under a goal; read, patch, archive by rep type id.
- Archiving a rep type keeps every rep it produced.

### Scheduling
- Schedule one rep, or bulk-schedule N consecutive days from one form.
- `duration_minutes` is copied from the rep type at creation, not taken from the client.
- Every create asserts `rep_type.goal_id == payload.goal_id` before inserting.

### Tracking
- Complete a rep (409 if it is not `pending`).
- Global "mark missed" sweep.
- Delete a rep, which also deletes its calendar event.

### Metrics — all computed at read time
- Daily score, week total (Mon-start), all-time weekly PR.
- First-rep-before-noon rate for the current week.
- Per-rep-type chain length, last completed date, and 60-day chain history.
- Per-goal 60-day and all-time cumulative progression (`completed − missed`).
- Current-calendar-month completion heatmap.
- Per-rep-type completion analytics, sorted by completion percentage.
- Week view: all seven days grouped by goal, with complete and delete inline.

### Debrief
- On-demand: text plus base64 MP3 plus week stats.
- Scheduled: Sunday email with MP3 attachment.

## Boundaries

### Building now
- Everything under Capabilities above. Chris confirmed on 2026-09-03 that the
  code is the authority on scope and `readme.md`'s out-of-scope list is stale:
  Analytics, WeekView, goal-progression charts and the month heatmap are real
  capabilities, not experiments.
- Rendering chains in the UI. They are computed, serialized, and currently
  thrown away — the highest-value gap in the product.

### Not yet
- **Push notification for the Sunday debrief.** Email with an MP3 attachment
  was a stopgap; push is still wanted. Do not architect the delivery path as
  email-only.
- Persisted `WeeklySummary` records. Specified in `readme.md`'s data model, not
  implemented — debriefs are ephemeral, so History cannot show past debriefs.
- Automatic 23:59 missed-rep sweep.
- Recurrence beyond "the next N consecutive days".
- ElevenLabs voice selection (voice id is hardcoded).

### Never
- Multi-user, teams, sharing, or account management.
- Two-way calendar sync. Calendar edits must never write back to the tracker.
- Native mobile app. The responsive web dashboard on a phone is the answer.
- Habit inference or automatic rep tagging.
- Cross-goal rep types. A rep type belongs to exactly one goal.
- Twilio phone calls.
- Non-Google calendars.
- Goal templates, marketplace, social features.
- Deleting or hiding a missed rep to protect a chain.

## Done Looks Like

V1 is shipped and in daily use as of 2026-09-03. These are the conditions that
still have to hold, stated so they can be checked rather than felt:

1. Creating a rep produces a gray Google Calendar event within one request, and
   the event id is persisted on the rep row.
2. Pressing ○ on a rep turns the calendar event green within 5 seconds.
3. Reps left pending at end of day are red in the calendar the next morning,
   without Chris pressing anything.
4. The Today view shows a per-rep-type chain length that does not read 0 for a
   chain that is actually alive.
5. The Sunday debrief arrives at 21:00 America/New_York and names chain lengths,
   week total against PR, first-rep rate, and the most-avoided rep type.
6. A rep that was missed is still visible as missed a month later.

### Fails if
- Chris stops opening the dashboard.
- The debrief reads as encouragement instead of findings.
- Calendar sync fails silently.
- A live chain displays as broken, making the dashboard feel unfairly red.
- Fake reps get written to keep a chain alive.
