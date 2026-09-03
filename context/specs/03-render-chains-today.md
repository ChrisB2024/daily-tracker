# Unit 03: Render Chains on Today

## Goal

Per-rep-type chains appear on the Today view. `/summary` already computes and
serializes them and two components are already written to draw them; the
dashboard imports neither. This is the smallest change with the largest product
effect in the plan.

## Design

Chains answer "is it still alive", which is a number, not a shape. So the
**number leads**:

- **`ChainsList` goes in `.dashboard-main`**, directly below `FirstRepStrip`
  and above `RhythmChart`. It renders name, goal, "N days" and the last
  completed date — the glance-value read.
- **`ChainsVisualization` goes in `.dashboard-sidebar`**, above
  `GoalProgressionsVisualization`. Its 240×100 sparklines are the trend read,
  and the sidebar is where trend already lives.

The sidebar currently renders only when `goal_progressions` is non-empty. Widen
that condition so the sidebar appears when **either** chains or progressions
have content, and each block inside renders independently.

**Colors must come from tokens.** Both components hardcode `#4ade80`, `#ef4444`,
`#333` and `#555` in SVG `stroke` and `fill` attributes. Replace with
`var(--completed)`, `var(--missed)`, `var(--border)` and `var(--pending)`
respectively. `#333` has no token and is used as an axis rule — use
`var(--border)`. This is the divergence named in `ui-context.md`; do not
propagate it.

**Empty state.** After Unit 02 a rep type with no completions appears at chain
0, so a truly empty list means no active rep types exist at all. Render a
`.empty` paragraph reading `No active rep types yet.` rather than an empty
panel — per the state-coverage rule in `ui-context.md`.

A chain of 0 is not an empty state. It renders as a row reading 0, because a
broken chain is exactly the information this view exists to deliver.

## Implementation

### `frontend/src/components/Dashboard.jsx`

Import `ChainsList` and `ChainsVisualization`. Place `<ChainsList chains={data.chains} />`
between `<FirstRepStrip />` and `<RhythmChart />`. Place
`<ChainsVisualization chains={data.chains} />` at the top of
`.dashboard-sidebar`, and change the sidebar's render condition from
`data.goal_progressions.length > 0` to a check that either collection is
non-empty.

### `frontend/src/components/ChainsList.jsx`

Add the empty-state branch. Confirm the existing markup against
`dashboard.css` — the `.chains`, `.chain`, `.chain-header`, `.chain-value` and
`.chain-last` classes already exist and are unused; verify they render as
intended rather than assuming.

### `frontend/src/components/ChainsVisualization.jsx`

Replace every hardcoded hex with the token equivalent. Add the empty-state
branch. Confirm `.chains-visualization`, `.chains-charts`, `.chain-chart` and
their children exist in the stylesheet.

### Do not

Change `/summary`, the chain math, or `RepItem`. If a chain renders wrong, the
defect is Unit 02's and belongs there.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| `chains` empty | Both components render their empty state | "No active rep types yet." |
| A chain has an empty `history` array | Chart guards and skips drawing rather than dividing by zero | The list row still renders its number; the chart slot is blank |
| Many rep types | The list grows the page; sparklines wrap in the sidebar | Longer scroll — acceptable, no virtualization |
| `/summary` fails | Existing error branch already covers the whole view | "Error: Failed to fetch summary" |
| Narrow viewport | Below 768px the sidebar stacks under main, per the single existing breakpoint | Chains list first, sparklines below |

## Threat Model

- **Data handled:** rep type names, goal titles and completion dates, rendered
  in the browser. No new data reaches the client — this payload is already sent
  and discarded.
- **Who can access it:** anyone who can open the dashboard, per S2. Unchanged.
- **Attacker controls the input:** rep type names and goal titles are
  user-authored text. React escapes them on render; **do not introduce
  `dangerouslySetInnerHTML`** to style a name or emoji.
- **Storage breached:** not applicable; this unit stores nothing.

## Dependencies

None. Both components exist; no charting library.

## Verify when done

**Technical**
- [ ] Chains render on Today with the correct number per rep type
- [ ] Sparklines render in the sidebar and match the list's numbers
- [ ] The sidebar appears when there are chains but no goal progressions
- [ ] Empty state renders when no active rep types exist
- [ ] A chain at 0 renders as a row reading 0, not as an empty state
- [ ] No hardcoded hex remains in either component
- [ ] Layout holds below 768px
- [ ] `npm run lint` passes, no console errors

**Security**
- [ ] Threat model run against the implementation
- [ ] No `dangerouslySetInnerHTML` introduced

**Product**
- [ ] Product invariant 4 now holds end to end — chains are independent *and* visible
- [ ] Remove the "chains are shown" row from Known Violations in `architecture.md`
- [ ] Chris confirms the number matches what he believes his real chain to be. **What surprised you?**
