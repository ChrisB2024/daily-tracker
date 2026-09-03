# Unit 08: Debrief Prompt and Tone

## Goal

The Sunday debrief reads like a friend who has been watching — specific,
quantified, behavioral. Today the prompt asks Claude for a "personal coach"
giving an "encouraging", "motivating" summary, which is precisely what
`readme.md` forbids, and "the Sunday debrief feels generic" is a listed
V1-failure condition.

## Reconcile before implementing

Written in a batch before Unit 07 was built. **Re-read the payload Unit 07
actually produces** and write the prompt against its real field names and
shapes, not the ones assumed here.

## Design

The output is spoken aloud as well as read, so it must work without visual
structure — no bullet points, no headers, no markdown. `readme.md` gives a
worked example of the target voice; use it as the style anchor in the prompt
itself rather than describing the voice abstractly.

Forbidden, explicitly: motivational quotes, emoji, praise, "great job", "keep it
up", exclamation marks, and any sentence that would read the same regardless of
the numbers. If a sentence survives swapping the data, it is filler.

Required: chain lengths by name, the week total against the PR, the first-rep
rate, the most-avoided rep type, and one closing question that names a specific
rep and a specific goal.

## Implementation

### `backend/app/services/debrief.py` — `generate_debrief_text`

Replace the prompt. Feed it the full Unit 07 payload rather than the three
counts it uses today. Structure the prompt as: the voice and the prohibitions,
the worked example from `readme.md`, then the week's data.

State the prohibitions as rules rather than preferences — "do not congratulate"
outperforms "try to stay neutral".

### Model and parameters

- Model `claude-opus-4-8` → **`claude-opus-5`**, the current default. Exact
  string, no date suffix.
- `max_tokens=300` is too tight for a debrief that now names chains, the PR
  comparison, the first-rep rate and a pattern. Raise to ~2000; the response
  will be far shorter, but a debrief truncated mid-sentence is a broken
  deliverable and this runs once a week.
- Adaptive thinking (`thinking={"type": "adaptive"}`) is worth enabling — this
  is pattern analysis over a week of behavior, not a formatting task. It costs
  latency and tokens on a weekly background job, which is the cheapest place in
  the system to spend both.
- Keep the existing `asyncio.to_thread` wrapper. The synchronous SDK inside a
  thread is the house pattern across all three integrations; do not introduce an
  async client for this one alone.

### Error text

`generate_debrief_text` currently returns the exception string as the summary
body on failure, so an API error is emailed to Chris as though it were his
debrief. Return a fixed sentence saying the debrief could not be generated, and
log the exception. **A secret must never reach the summary body** — an
authentication failure's message is exactly the kind of thing that leaks a key
into an email.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| Anthropic unreachable or rate-limited | Caught; fixed failure sentence returned; exception logged | "This week's debrief could not be generated." No numbers invented. |
| API key missing | Existing early return, unchanged | The configuration message |
| Response hits `max_tokens` | Truncated mid-sentence | Raise the ceiling; check `stop_reason` and log when it is not `end_turn` |
| Model returns praise anyway | Not detectable automatically | Judged by reading it — the acceptance check below is qualitative on purpose |
| A week with zero reps | Prompt must handle it without inventing activity | A debrief that says the week was empty |
| Auth error text leaks into the summary | Prevented by the fixed failure sentence | Never sees the raw error |

## Threat Model

- **Data handled:** the Unit 07 aggregate payload — counts, chain lengths, rep
  type names, goal titles. Goal titles leave the system to Anthropic, and again
  to ElevenLabs inside the generated text.
- **Who can access it:** `GET /debrief` is open per S2; the emailed copy goes to
  `settings.smtp_user`, which is Chris's own address.
- **Attacker controls the input:** rep type names and goal titles are
  user-authored and are interpolated into a prompt. Since the only author is
  Chris, prompt injection is self-inflicted at worst — but keep the data in a
  clearly delimited section of the prompt rather than sentence-spliced, so this
  stays true if the trust model ever changes.
- **Storage breached:** nothing stored yet. Unit 11 persists this text; its
  threat model must account for a stored behavioral profile.

## Dependencies

- Unit 07 complete and verified.
- No new packages. `anthropic` is already a dependency.

## Verify when done

**Technical**
- [ ] Model is `claude-opus-5`
- [ ] `max_tokens` raised; `stop_reason` checked and logged when not `end_turn`
- [ ] A generated debrief for a real week names chain lengths, the PR comparison, the first-rep rate and the most-avoided rep type
- [ ] A forced API failure returns the fixed sentence, and the exception appears in logs, not in the summary
- [ ] A zero-rep week produces coherent output

**Security**
- [ ] Threat model run against the implementation
- [ ] No exception text, key fragment or configuration value can reach the summary body or the email
- [ ] No rep `notes` in the prompt

**Product**
- [ ] Product invariant 6 holds: read the output — no praise, no emoji, no motivational language, and no sentence that would survive swapping the data
- [ ] Chris reads a real debrief and confirms it sounds like findings. **What surprised you?**
- [ ] Remove the debrief-tone row from Known Violations in `architecture.md`
