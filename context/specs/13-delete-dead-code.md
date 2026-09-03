# Unit 13: Delete Dead Code

## Goal

Nothing in the repo lies about what it does. Remove the unreachable
server-rendered dashboard, rewrite a README that is a completed TODO list, and
clear the stale comments and duplicated functions that make a cold read
misleading.

## Reconcile before implementing

Written first, executed last, and every unit before it touches these files.
**Re-verify each item below is still dead before deleting it** — Unit 03 wires
in components listed here as dead in an earlier draft, and later units may have
made use of something. Deleting on the strength of this spec alone, months
after it was written, is exactly how working code gets removed.

Confirm each with a grep, not from memory.

## Design

No user-visible change. If anything looks different afterwards, something was
deleted that was not dead.

## Implementation

Work in separate commits, one group at a time, verifying the app boots and every
view works between each. A single sweeping commit makes a bisect impossible when
something turns out not to have been dead.

### The server-rendered dashboard

`routers/dashboard.py` is not registered in `main.py`, so `/` is unreachable and
the Jinja dashboard has been dead since the React SPA landed. Remove:

- `backend/app/routers/dashboard.py`
- `backend/app/templates/dashboard.html`
- `backend/app/static/style.css`

Then check what falls out: `main.py` mounts `StaticFiles(directory="app/static")`
— if nothing else serves from there, remove the mount and the `StaticFiles`
import. `jinja2` is a declared dependency in `pyproject.toml`; if nothing else
imports it, remove it too, per the "install dependencies just in time" rule read
in reverse.

Confirm before deleting: no template is referenced anywhere else, and no
deployment serves `/`.

### `backend/README.md`

It is the Slice-1 TODO list, every item long since done, and it tells the reader
to open `http://localhost:8000` for a dashboard that is no longer served.
Rewrite as: what the service is, how to run it locally, how to run migrations,
where the environment variables come from, and a pointer to `context/` for
everything else. Keep the OAuth script instructions — they are still correct and
still needed.

Fix the port confusion while here: the Vite dev proxy targets `localhost:8001`,
the README says 8000, and the Dockerfile declares `EXPOSE 8080` while binding
8000. Pick one dev port, make the README and `vite.config.js` agree, and correct
the `EXPOSE` line.

### Stale comments

- `backend/app/models/rep_type.py` — `# TODO (Chris):` on columns that are all
  implemented. Delete the TODO prefix, keep any line that still explains *why*.
  The note that multiple rep types per goal may be flagged `is_first_rep` is
  worth keeping.
- `backend/app/models/rep.py` — same treatment.
- `backend/app/config.py` — an unanswered TODO asking why `settings` is a
  module-level singleton. Either answer it in a sentence or delete it.
- `backend/alembic/env.py` — references `models/task.py`, which never existed
  under that name. Correct to `models/rep.py`.

### `print()` → `logging`

`scheduler.py`, `services/email.py` and `services/debrief.py` use bare `print()`;
`services/google_calendar.py` uses `logging`. Logging is the chosen convention
per `code-standards.md`. Convert, using module-level
`logger = logging.getLogger(__name__)` and appropriate levels — `info` for
"scheduler started", `error` for a failed send. Check no converted line can
carry a secret.

### Duplicate audio functions

`generate_debrief_audio_bytes` and `generate_debrief_audio` in
`services/debrief.py` differ only in returning raw bytes versus base64. Keep one
that returns bytes; base64-encode at the one call site that needs it. Verify
both current callers — the scheduler and `get_debrief` — still work.

### Deprecated startup hook

`main.py` uses `@app.on_event("startup")` / `("shutdown")`, deprecated in favour
of a lifespan context manager. Convert both into one `lifespan` handler and pass
it to `FastAPI(lifespan=...)`. This changes process startup, so verify the
scheduler still registers its jobs and the app still boots in the container.

### CORS

`allow_origins=["*"]` with `allow_credentials=True` is a combination browsers
reject, so the credentials flag does nothing today and the config misstates the
intent. Set it to what is actually meant: open origins, no credentials. Behavior
is unchanged; the file stops lying.

## Out of scope

Do **not** remove `frontend/public/icons.svg` or `favicon.svg` without checking
`index.html` — a favicon referenced from HTML will not show up in a component
grep.

Do **not** add a test suite, a typechecker or CI here. That is its own decision,
listed under "Not units yet" in the build plan.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| Something deleted was not dead | Import error at boot, or a 404 on a live route | Caught by booting and clicking every view between commits |
| `StaticFiles` mount removed while something serves from it | 404 on that asset | Grep for `/static` across both halves before removing |
| Lifespan conversion drops the scheduler | Jobs never register; no error | Explicitly assert both jobs exist at startup after converting |
| A converted log line carries a secret | Silent leak into logs | Read every converted line before committing |
| Dev port change breaks Chris's local flow | Frontend cannot reach the API | Update `vite.config.js` and the README in the same commit |

## Threat Model

- **Data handled:** none directly. This unit changes what is logged, which is
  where secrets leak if a converted line interpolates a config value or an
  exception from an authenticated call.
- **Who can access it:** removing the unregistered dashboard router and the
  static mount **reduces** attack surface. The CORS correction changes a
  misleading declaration, not effective behavior.
- **Attacker controls the input:** unchanged. No new input path.
- **Storage breached:** unchanged.

## Dependencies

None in packages. Sequenced last because it touches files every other unit
edits.

## Verify when done

**Technical**
- [ ] Every deletion confirmed dead by grep immediately beforehand, not from this spec
- [ ] App boots; all seven views work; `/healthz` responds
- [ ] Both scheduler jobs register after the lifespan conversion
- [ ] No `print()` remains in a service or the scheduler
- [ ] One audio function; both callers work
- [ ] `vite.config.js`, `backend/README.md` and the Dockerfile agree on ports
- [ ] `npm run lint` passes
- [ ] Container builds and boots

**Security**
- [ ] Threat model run against the implementation
- [ ] Every converted log line reviewed for secrets
- [ ] Static mount removed only after confirming nothing serves from it

**Product**
- [ ] No user-visible change whatsoever
- [ ] `backend/README.md` describes the system as it is
- [ ] Clear the corresponding entries from Known Debt in `progress-tracker.md`
- [ ] Remove the CORS row from Known Violations in `architecture.md`
