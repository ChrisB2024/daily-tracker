# Unit 12: Past Debriefs in History

## Goal

The History view lists past weeks and renders each stored debrief, so the record
Unit 11 persists becomes something Chris can actually read.

## Reconcile before implementing

Written before Unit 11 existed. **Read the `WeeklySummary` model as built** —
particularly whether `text_summary` was stored at all, since Unit 11 raises an
open question about whether prose belongs in an unauthenticated database. If
that ruling excluded the text, this unit renders structured stats only, and the
Design below needs rewriting first.

## Design

History currently renders all-time per-goal progression charts. Debriefs are a
second, different kind of history: chronological, textual, one entry per week.
Add them as a distinct section above the progression charts — the most recent
week first, since that is what gets reread.

Each entry shows the week range as its heading, then the debrief text. Render
the text as plain paragraphs; it is prose written to be spoken, so it needs
comfortable measure and line height, not the dense treatment the stat surfaces
use. Use `--fg` for the body and `--muted` for the week range and metadata.

Collapsed by default beyond the most recent, or all expanded? Prefer showing the
most recent expanded and older ones as clickable week headings — a page of six
months of prose is not scannable.

**Empty state:** `No debriefs recorded yet.` with a line noting they are
generated each Sunday. Never an empty panel.

**Do not** show a "regenerate" button. Regeneration would overwrite the stored
record and costs an API call per click.

## Implementation

### Backend — a list endpoint

Add to `routers/history.py`, keeping its existing shape:

`GET /history/debriefs` → most recent first, each carrying `week_start_date`,
`week_end`, `text_summary`, the stats needed for display, and `delivered_at`.

Paginate with a `limit` query parameter defaulting to something small. At one
user's rate this is 52 rows a year, so this is cheap insurance rather than a
requirement.

Define an explicit Pydantic response model, as every other router does. **Do not
return the ORM object directly** — that would expose whatever columns Unit 11
happened to add.

### Frontend

- `api.js` — add `getDebriefHistory()`, matching the existing one-function-per-endpoint
  pattern. No component gets a URL.
- `History.jsx` — fetch both progressions and debriefs. Keep the existing
  loading and error branches covering both; a failure in either shows the
  view-level error rather than a half-rendered page.
- Render the text with React's default escaping. **No `dangerouslySetInnerHTML`.**
  It is model output; it must never be interpreted as markup.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| No debriefs stored | Empty array | "No debriefs recorded yet." |
| Debriefs stored but progressions empty | Sections render independently | Debriefs shown, progression area in its own empty state |
| A row from before a payload change | Missing fields tolerated, not crashed on | The entry renders with what it has |
| Either fetch fails | View-level error branch | "Error: Failed to fetch history" |
| A very long debrief | Wraps; page grows | Collapsed older entries keep it scannable |
| `text_summary` contains markup-like characters | Escaped by React | Rendered literally, as text |

## Threat Model

- **Data handled:** stored debrief text — the behavioral profile flagged in
  Unit 11 — now rendered in a browser.
- **Who can access it:** anyone who can open the dashboard, per S2. This unit
  makes the profile *browsable*, which is a real increase in exposure over
  having it merely stored. If Unit 11's S2 ruling was conditional, re-check it
  here before shipping.
- **Attacker controls the input:** the text is model output derived from
  user-authored goal titles. React escaping is the control, and it is sufficient
  as long as nothing reaches for `dangerouslySetInnerHTML`.
- **Storage breached:** unchanged from Unit 11.

## Dependencies

- Unit 11 complete.
- No new packages.

## Verify when done

**Technical**
- [ ] `GET /history/debriefs` returns stored debriefs, most recent first
- [ ] The endpoint returns a defined response model, not the ORM object
- [ ] History renders debriefs above progressions
- [ ] Empty state renders when none are stored
- [ ] A row missing a newer field renders without crashing
- [ ] Layout holds below 768px
- [ ] `npm run lint` passes, no console errors

**Security**
- [ ] Threat model run against the implementation
- [ ] No `dangerouslySetInnerHTML` anywhere in the render path
- [ ] Unit 11's S2 ruling re-confirmed now the data is browsable

**Product**
- [ ] `readme.md` Slice 5 item 21 ("History view — past weeks, past debriefs") now holds
- [ ] Colors from tokens only
- [ ] `project-overview.md` "Not yet" entry for persisted summaries moves to shipped
