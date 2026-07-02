# Daily Tracker

A personal, goal-driven **rep tracker** with bidirectional psychological pressure: complete your reps and watch them turn green in your calendar, miss them and watch them go red. Every Sunday, get an audio debrief that tells you your chain lengths, your weekly PR, and which reps you're avoiding.

Built for one user (me). Local-first, no multi-tenancy, no auth beyond a single Google account.

---

## Why This Exists

Habit trackers track inputs. Project trackers track outputs. Task managers track noise. None of them capture the thing that actually moves goals forward: **the rep**.

A rep is one binary, scoped unit of work — 15 to 90 minutes, done or not done, producing visible output. "Work on Hiclone" is not a rep, it's a vibe. "5 cold sends logged with who+what" is a rep.

This tool exists to:

1. Force every rep to be tagged to a goal (no orphan work)
2. Make completion *visible* in the calendar I already check — gray when planned, green when done, red when missed
3. Score every day by reps completed, and chase weekly PRs the same way I chase 5lb on a lift
4. Protect independent chains per rep type, so missing one doesn't kill them all
5. Surface the gap between *what I committed to* and *what I actually did* in a Sunday debrief that quantifies it

The Sunday debrief is the point. The daily dashboard is the input layer that makes the debrief possible.

---

## Core Philosophy

- **Reps over tasks.** A rep is binary, scoped, and produces visible output. If you can't write its done/not-done criterion in one line, it's not a rep.
- **Goal-centric, not habit-centric.** Habits are inputs. Goals are outcomes. Every rep ladders to a goal.
- **Treat each domain like a training block.** Goals contain named reps. Reps have cadences. The daily tracker is the scoreboard.
- **One chain per rep type, not per day.** Missing a Build rep doesn't kill your Outbound streak. Each chain lives independently — and you'll feel each one.
- **Daily score, weekly PR.** Each rep = 1 point. Daily floor keeps you above zero; weekly PR is the dopamine. Same loop as adding 5lb to a lift.
- **First rep before noon is non-negotiable.** Starting is 80% of the lift. Walking into the gym is the hard part.
- **Make missed reps visible, not invisible.** Erasing a missed rep erases the evidence. Missed reps stay red so pattern detection works.
- **The calendar is a mirror, not a source.** The tracker is the brain. Calendar reflects state, doesn't drive it.
- **Behavioral evidence over self-report.** The Sunday summary uses actual rep data, not how I feel about my week.
- **Mirrors, not monitors.** The tool shows me what I'm doing — it doesn't nag, gamify, or guilt.

---

## The Rep System

### Definitions

**Goal** — a desired outcome with a target date and status. Examples: "Ship DD Agent to first paying client", "Land 3 plumbing clients for PlumbLine".

**Rep Type** — a named, binary unit of work attached to a goal. Defined by:
- A **name** ("Outbound rep", "Build rep", "Skill rep")
- A **one-line criterion** ("5 cold sends logged with who+what")
- An **estimated duration** (15-90 minutes)
- A **cadence** (daily floor and/or weekly target)
- An optional **first-rep flag** (is this the morning non-negotiable for this goal?)

**Rep** — a scheduled instance of a Rep Type. Goes into the calendar. Has a status: pending, completed, or missed.

### The Test

If you can't write the done/not-done criterion in one line, it's not a rep. "Work on PlumbLine" fails. "1 spec section closed OR 1 module to green tests" passes.

### User-Defined, Not Hardcoded

Goals and their rep types are defined by the user through the UI and saved. They can be added, edited, paused, or archived at any time. No globally shared rep type vocabulary — every goal defines its own 3-5 reps from scratch. This keeps the system honest: you write the contract for each domain.

### Example Goal with Reps

```
Goal: Ship DD Agent to first paying client (target: June 15)
  ├─ Outbound rep    │ 5 cold sends logged with who+what    │ daily floor: 1
  ├─ Build rep       │ 1 spec section closed OR 1 module green │ daily floor: 1  [first-rep]
  ├─ Demo rep        │ 1 loom/recording/asset for outbound   │ weekly target: 2
  └─ Follow-up rep   │ 3 replies to existing threads         │ daily floor: 1
```

---

## Scope (V1)

### In Scope

- Goal CRUD
- Rep Type CRUD per goal (user-defined, editable any time)
- Rep scheduling — schedule a Rep Type as a Rep on a specific date/time
- Google Calendar one-way sync (tracker → calendar) with status-driven color updates
- Per-rep-type chain tracking (independent streaks)
- Daily score + weekly PR display
- First-rep-before-noon dashboard section
- End-of-day cron to mark unfinished reps as missed
- Daily dashboard: today's reps grouped by goal, chains per rep type, 30-day rhythm chart
- Weekly Sunday debrief: text + audio, with quantified chain status and weekly PR
- Push notification on Sunday at 21:00
- Single-user, single Google account, local deployment

### Out of Scope (V1)

- Multi-user, auth, teams, sharing
- Two-way calendar sync (Google Calendar edits do not update the tracker)
- Mobile native app (web dashboard accessed on phone is fine)
- Habit inference / auto rep tagging
- Twilio phone calls (push notification is enough for v1)
- Integration with other calendars (Outlook, Apple, etc.)
- Goal templates, marketplace, social features
- Cross-goal rep types (each rep type belongs to exactly one goal)
- Analytics beyond rhythm chart, chains, and weekly insights

---

## System Architecture

```
┌─────────────────────┐
│   Web Dashboard     │  React or vanilla HTML/JS
│   (browser)         │  Goal + RepType + Rep UI, check-offs
└──────────┬──────────┘
           │ HTTP
           ▼
┌─────────────────────┐
│   FastAPI Backend   │  Async, single process
│                     │  /goals, /rep-types, /reps, /summary
└──────────┬──────────┘
           │
     ┌─────┼─────────────────┬──────────────────┐
     ▼     ▼                 ▼                  ▼
  ┌─────┐ ┌──────────┐  ┌─────────────┐  ┌──────────────┐
  │ PG  │ │ Calendar │  │ Claude API  │  │ ElevenLabs   │
  │ DB  │ │ Client   │  │ (debrief)   │  │ (TTS audio)  │
  └─────┘ └─────┬────┘  └─────────────┘  └──────────────┘
                │
                ▼
        ┌───────────────┐
        │ Google Cal API│
        └───────────────┘
```

### Components

**Web Dashboard** — single-page interface. Three views: Today (default), Goals (manage goals + rep types), History (past weeks + debriefs). Mobile-responsive since I'll check it on my phone in the morning.

**FastAPI Backend** — async, single process. Owns the data model, computes chains and scores on read, orchestrates external API calls.

**Postgres** — goals, rep types, reps, weekly summaries.

**Calendar Client** — thin wrapper around Google Calendar API. OAuth refresh, event create/update/delete, color updates.

**Claude API** — generates the Sunday debrief from structured weekly rep data.

**ElevenLabs (or system TTS)** — converts debrief text to audio. Optional for v1.

---

## Data Model

```
Goal
  id: UUID
  title: str
  description: str (nullable)
  target_date: date (nullable)
  status: enum (active | paused | completed | archived)
  created_at: datetime

RepType
  id: UUID
  goal_id: UUID (FK, NOT NULL)
  name: str                    # "Outbound rep"
  criterion: str               # one-line done/not-done definition
  duration_minutes: int        # 15-90 typical
  daily_floor: int (nullable)  # minimum reps per day
  weekly_target: int (nullable) # target reps per week
  is_first_rep: bool           # is this THE morning rep for the goal?
  emoji: str (nullable)        # for dashboard rendering
  display_order: int
  status: enum (active | archived)
  created_at: datetime

Rep
  id: UUID
  rep_type_id: UUID (FK, NOT NULL)
  goal_id: UUID (FK, NOT NULL — denormalized for fast queries)
  scheduled_date: date
  scheduled_time: time
  duration_minutes: int        # copied from rep_type at creation
  calendar_event_id: str       # Google Calendar event ID
  status: enum (pending | completed | missed)
  completed_at: datetime (nullable)
  notes: text (nullable)       # for who+what logging on outbound reps, etc.
  created_at: datetime

WeeklySummary
  id: UUID
  week_start_date: date
  rep_data: JSON               # per-rep-type stats: chain length, count, PR comparison
  patterns: JSON               # avoided / dominant rep types, first-rep rate
  text_summary: str            # full Claude-generated debrief
  audio_url: str (nullable)
  delivered_at: datetime (nullable)
```

**Key constraints:**
- `RepType.goal_id` NOT NULL. Every rep type belongs to one goal.
- `Rep.rep_type_id` and `Rep.goal_id` both NOT NULL. No orphan reps. No untyped reps.
- Status is tri-state: `pending → completed` OR `pending → missed`. No deletion of missed reps.
- `RepType.criterion` is required at creation. The schema enforces "is this a rep or a vibe?"
- Chains, scores, and PRs are computed at read time, never stored on the Rep record.

---

## Calendar Sync Model

One-way: tracker → Google Calendar. Tracker is source of truth.

### Color Mapping

| Rep Status | Google Color ID | Color Name | When Applied |
|---|---|---|---|
| `pending`   | 8  | Graphite (gray) | On rep creation |
| `completed` | 10 | Basil (green)   | When checked off in tracker |
| `missed`    | 11 | Tomato (red)    | End-of-day cron at 23:59 |

### Event Title Format

`[<RepType>] <Goal title or rep description>`

Examples:
- `[Outbound] 5 cold sends — DD Agent`
- `[Build] Ingestion module to green tests`
- `[Session] Muay Thai training`

The bracket prefix makes rep type scannable in calendar view at a glance.

### Lifecycle

```
Create rep
  → INSERT into reps (status=pending)
  → Google Calendar: events.insert
       title:   "[<RepType.name>] <description>"
       colorId: 8
       extendedProperties.private.rep_id: <rep.id>
  → Store returned event.id as rep.calendar_event_id

Check off rep
  → UPDATE reps SET status=completed, completed_at=now()
  → Google Calendar: events.patch with colorId=10

End-of-day (23:59 local time)
  → For each pending rep where scheduled_date = today:
      → UPDATE reps SET status=missed
      → Google Calendar: events.patch with colorId=11
```

---

## Chains, Scores, and PRs

These are the psychological core. All computed at read time from the `reps` table.

### Chain (per Rep Type)

For a given Rep Type, the chain is the longest unbroken consecutive-days streak where at least one rep of that type was completed. Each rep type has its own chain. Missing a Build rep does not break the Outbound chain.

A chain breaks when a day passes with zero completions of that rep type, AND that rep type had a daily floor > 0.

Rep types with only a weekly target (no daily floor) compute their chain on a per-week basis instead.

### Daily Score

Sum of completed reps across all rep types for a given day. Each rep = 1 point. Displayed as a large number at the top of the Today view.

### Weekly Total + PR

Sum of completed reps for the current week (Mon-Sun). Compared against the all-time best weekly total (the PR). Beating the PR is the dopamine.

### First-Rep Rate

Per week, the percentage of days where every rep type flagged `is_first_rep = true` was completed before noon local time. This is the headline behavioral metric.

---

## Sunday Debrief

Runs every Sunday at 21:00 local time.

### Pipeline

```
1. Query: all reps for the past 7 days, grouped by goal and rep type
2. Compute per-rep-type stats:
   - Current chain length (and change vs. last week)
   - Reps completed vs. weekly target / daily floor expectation
   - Missed reps with date
3. Compute weekly totals:
   - Total reps completed
   - Comparison to all-time PR
   - First-rep-before-noon rate
4. Compute behavioral patterns:
   - Longest chain this week
   - Broken chains this week (and when they broke)
   - Most-completed rep type
   - Most-avoided rep type (across all goals)
   - Correlation: did missing first-rep days correlate with low total-rep days?
5. Send structured data to Claude API with debrief prompt
6. Receive text summary
7. (Optional) Pipe through ElevenLabs for audio
8. Send push notification + dashboard banner
9. Store WeeklySummary record
```

### Debrief Tone

The summary should sound like a friend who's been watching, not a productivity app. Specific, quantified, behavioral. No motivational quotes. No emojis. No "great job!" — just findings, chains, numbers, and patterns.

### Example Output Target

> Chris — weekly total: 23 reps. Below your PR of 28 but above floor (15).
>
> Chains: Outbound rep at 6 days, longest this quarter. Session rep at 12 days, matched PR. Build rep broken Tuesday, restarted Wednesday — back to 4 days. Skill rep broken Thursday, not yet restarted.
>
> First-rep-before-noon rate: 5/7 days (71%). The two days you missed the first rep, total reps for that day were 1 and 2. Pattern confirmed: starting predicts the day.
>
> Most-completed: Session rep (5/5). Most-avoided: Outbound rep on the PlumbLine goal — 2 of 5 targeted days, third week below floor. Pattern is consistent.
>
> Worth asking: what is the first PlumbLine rep, and why isn't it happening before noon?

---

## Build Order

Vertical slices, smallest viable thing first.

### Slice 1 — Foundation (no calendar yet)
1. FastAPI scaffolding, Postgres setup, SQLAlchemy async models
2. Goal CRUD endpoints
3. RepType CRUD endpoints (nested under goals)
4. Rep create + check-off endpoints
5. Minimal HTML dashboard: list goals + rep types, schedule reps, check them off
6. Manual end-of-day "mark missed" endpoint

### Slice 2 — Calendar Integration
7. Google OAuth setup, token storage
8. `GoogleCalendarClient` wrapper class
9. Hook calendar event create on rep creation (with rep type prefix in title)
10. Hook color update on rep completion
11. End-of-day cron with color update for missed reps

### Slice 3 — Visual Dashboard
12. Build out the full dashboard (matches mockup):
    - Header with daily score + week count + weekly PR
    - First-rep status strip
    - Goals section with rep type chains
    - Today's reps grouped by goal
    - 30-day rhythm bar chart

### Slice 4 — Sunday Debrief
13. Chain / score / PR computation queries
14. Pattern detection logic (avoidance, first-rep correlation)
15. Claude API prompt + integration for debrief text
16. Cron at Sunday 21:00 to trigger the pipeline
17. Push notification delivery
18. (Optional) ElevenLabs audio generation

### Slice 5 — Quality of Life
19. Goal + RepType management UI (create, edit, archive)
20. Rep scheduling UI with time picker and recurrence ("schedule daily for the next 2 weeks")
21. History view (past weeks, past debriefs, all-time chain records)

---

## Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | FastAPI (async) | Default stack; async needed for external API calls |
| ORM | SQLAlchemy 2.x (async) | Default stack |
| DB | Postgres (local) | Default stack, structured data |
| Frontend | Vanilla HTML/JS or React | Single user, no need for heavy framework v1 |
| Calendar | Google Calendar API v3 | Already use Google Calendar |
| LLM | Anthropic Claude API | Best for quantified behavioral summary |
| TTS (optional) | ElevenLabs | High-quality voice, fall back to system TTS |
| Scheduler | APScheduler or cron | Two jobs: 23:59 daily, Sunday 21:00 |
| Hosting | Localhost or single VPS | Personal use only |

---

## Success Criteria

V1 ships when:
- I can create a goal, add 3-5 rep types to it, and schedule reps from those types
- Reps appear in my Google Calendar in gray on creation with `[RepType]` prefix
- Checking a rep off turns it green in Calendar within 5 seconds
- Unfinished reps turn red at 23:59
- Dashboard shows independent chains per rep type, daily score, weekly PR, and first-rep status
- I receive a Sunday 21:00 notification with a debrief that quantifies chains, weekly total vs. PR, and avoidance patterns
- I use it for 4 consecutive weeks without breaking

V1 fails if:
- I forget the dashboard exists after week 2
- The Sunday debrief feels generic (motivational platitudes instead of quantified findings)
- Calendar sync lags or silently fails
- Chains feel unfair (e.g., one broken type makes the whole dashboard feel red)
- I find myself disabling the tracker rather than confronting what it shows me
- I start writing fake reps to keep chains alive (the criterion-line discipline failed)

---

## Open Questions

- **Audio delivery channel** — push notification with link to web-hosted audio file, or just text? Decide before Slice 4.
- **Goal pause vs. archive** — should "paused" goals show up in the Sunday debrief at all? Lean toward hiding paused, never archive without explicit confirmation.
- **Recurring rep scheduling** — best UX for "schedule Outbound rep daily for the next 2 weeks"? Decide before Slice 5.
- **Chain rules for weekly-only rep types** — confirm: chain advances per *week* hit, breaks if a week ends below weekly target. Edge cases TBD.
- **First-rep enforcement** — purely informational, or does the dashboard visually lock until first reps are done? Lean toward informational.

---

## Non-Negotiables

- **Every rep tagged to a Rep Type, every Rep Type tagged to a Goal.** No orphans, no untyped reps. Schema-enforced.
- **Every Rep Type has a one-line binary criterion.** If you can't write it, it's not a rep — it's a vibe.
- **Reps are binary, scoped, and 15-90 minutes.** Anything longer gets split. Anything vaguer gets refined or rejected.
- **Missed reps stay visible (red), not deleted.**
- **Chains are independent per rep type.** Missing one never breaks another.
- **First rep before noon is non-negotiable.** Tracked, displayed, debriefed on.
- **Sunday debrief uses rep data, never self-report.**
- **Calendar is mirror, not source. One-way sync.**
- **Tool stays simple. No feature creep.** If it's not in scope for V1, it waits.