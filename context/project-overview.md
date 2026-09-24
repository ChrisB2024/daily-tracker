# Daily Tracker

Recovered from the codebase and `readme.md` on 2026-09-07. Scope and status
confirmed by Chris; everything else is observed from code.

> **Direction changed 2026-09-24.** Google Calendar is now the input and the
> tracker the scoreboard: `[Goal] …` events become tasks, checked off at end of
> day, shown as a points-and-lines graph. See
> `specs/14-calendar-first-redesign.md`. This file describes the rep system as
> shipped; its Core Flow, Capabilities and Never list are rewritten unit by unit
> as the redesign lands. "Two-way calendar sync" left the Never list in Unit 15.

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

Since the calendar-first redesign (Units 14–20, 2026-09-24):

1. Open **Goals** and create a goal. Its card shows the calendar tag to use, e.g. `[Hitwin]`.
2. Plan the day in Google Calendar: events titled `[Goal title] what you're doing` on the primary calendar.
3. Open **Today**. It syncs once on open (and every 15 minutes in the background) and lists the day's tasks grouped by goal.
4. At the end of the day, tick what you did. The task goes `completed` and its calendar event turns green (`colorId: 10`).
5. At 00:00 the previous day's unticked tasks become `missed` and turn red (`colorId: 11`).
6. A task whose event was deleted shows under "Removed today — why?" and takes a one-line reason until midnight.
7. Click the date on Today for the **graph**: goals as clusters, tasks as points. Switch to **Week** for Monday–Sunday and the goal ranking by time completed.

The original rep flow (rep types, Schedule, chains, Sunday debrief) is retired;
its history stays in the database and in History, Analytics and Week.

## Capabilities

### Goals and rep types
- Create, list, read, patch goals. Duplicate titles rejected with 409.
- Delete a goal: soft by default (`status = archived`), or `?hard=true` to purge its rep types and reps permanently.
- Create and list rep types under a goal; read, patch, archive by rep type id.
- Archiving a rep type keeps every rep it produced.

### Scheduling — retired from the UI in Unit 20
- The API still accepts `POST /reps` and `/reps/bulk`; nothing in the UI calls them.

### Tracking
- Complete a rep (409 if it is not `pending`).
- Global "mark missed" sweep.
- Delete a rep, which also deletes its calendar event.

### Tasks (calendar-first redesign, since Unit 15)
- Events on the primary Google Calendar titled `[Goal] …` are pulled in as
  pending tasks every 15 minutes, or now via `POST /tasks/sync`.
- `GET /tasks?date=` lists a day's tasks with their goal titles.
- A pending task follows its event when it moves; it is cancelled when the
  event is deleted. Finished tasks never change.
- A goal with tasks cannot be hard-deleted (409); archive it instead.
- Today opens with the day's tasks grouped by goal, syncing once on open, with
  a Sync button, the last-synced time, a note naming any `[Tag]` that matched
  no goal, and a "Removed today — why?" list.
- Check a task off until midnight (`POST /tasks/{id}/complete`); its event
  turns green. At 00:00 the previous day's unchecked tasks become missed and
  turn red.
- A task removed from the calendar takes a one-line reason until the end of
  its day; after that the question is dropped.

### Metrics — all computed at read time
- Daily score, week total (Mon-start), all-time weekly PR.
- First-rep-before-noon rate for the current week.
- Per-rep-type chain length, last completed date, and 60-day chain history.
- Per-goal 60-day and all-time cumulative progression (`completed − missed`).
- Current-calendar-month completion heatmap.
- Per-rep-type completion analytics, sorted by completion percentage.
- Week view: all seven days grouped by goal, with complete and delete inline.

### Debrief — retired in Unit 20
- No Sunday email and no Debrief tab. `GET /debrief` still exists; past
  debrief numbers remain visible in History.

## Boundaries

### Building now
- Everything under Capabilities above. Chris confirmed on 2026-09-07 that the
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
- Native mobile app. The responsive web dashboard on a phone is the answer.
- Habit inference or automatic rep tagging.
- Cross-goal rep types. A rep type belongs to exactly one goal.
- Twilio phone calls.
- Non-Google calendars.
- Goal templates, marketplace, social features.
- Deleting or hiding a missed rep to protect a chain.

## Done Looks Like

V1 is shipped and in daily use as of 2026-09-07. These are the conditions that
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
