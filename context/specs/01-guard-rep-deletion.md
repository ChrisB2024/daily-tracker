# Unit 01: Guard Rep Deletion

## Goal

`DELETE /reps/{rep_id}` accepts only `pending` reps and returns 409 for
`completed` or `missed` ones, and the ✕ button stops rendering on non-pending
rows in Today and Week. Restores the "missed reps stay visible" non-negotiable,
which one click currently defeats.

## Design

No new UI. `RepItem` already receives the rep's status and already disables its
status button for non-pending reps — the delete button gains the same
conditional. Removing the control entirely is correct rather than disabling it:
a disabled ✕ invites a click and explains nothing, whereas its absence matches
the fact that the action does not exist for that rep.

Spacing must not shift when the button is absent. Whatever layout rule
`.rep` uses, a completed row has to line up with a pending one above it —
check this visually, not just in the DOM.

## Implementation

Backend first, verified, then the UI. The guard is the protection; the button
removal is cosmetic and worthless on its own.

### `backend/app/routers/reps.py` — `delete_rep`

Immediately after the existing 404 check, before any calendar call:

```python
if rep.status != RepStatus.pending:
    raise HTTPException(
        status_code=409,
        detail=f"Cannot delete a {rep.status.value} rep",
    )
```

Mirrors the 409 already in `complete_rep`, including the message shape. Nothing
else in the handler changes — a pending rep still deletes its calendar event
and its row.

### `frontend/src/components/RepItem.jsx`

`isPending` is already computed. Wrap the delete button so it renders only when
`isPending` is true. Leave the status button, the `[RepType]` label and the time
untouched.

### Callers

`TodayReps.jsx` and `WeekView.jsx` keep passing `onDelete` unchanged — the
decision lives in `RepItem`, so both views inherit it and cannot drift apart.
Their `confirm("Delete this rep? This cannot be undone.")` stays as-is.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| Unknown `rep_id` | Existing 404, unchanged | "Failed to delete rep" |
| Rep is completed or missed | 409 before any mutation or calendar call | Nothing — the button is gone. Reachable only via the API directly, which returns the 409. |
| Two deletes race on one pending rep | Second finds no row, 404s | "Failed to delete rep" |
| Google Calendar unreachable during a valid delete | `delete_event` swallows and logs; the row is still deleted | Rep disappears; the calendar event is orphaned. **Pre-existing behavior, not fixed here** — see Unit 10. |
| Frontend stale, rep completed in another tab | Button absent after refetch; a direct call 409s | Row updates on next refetch |

## Threat Model

- **Data handled:** one `reps` row and its `calendar_event_id`.
- **Who can access it:** anyone with the API URL. The API is deliberately
  unauthenticated (`architecture.md` S2), so this unit does not add an access
  control — it narrows what the existing open endpoint can destroy, from every
  rep to pending reps only.
- **Attacker controls the input:** `rep_id` is parsed as a UUID by FastAPI, so
  it cannot be injected. The worst case shrinks from "erase the entire evidence
  trail" to "erase reps not yet acted on", which is recoverable by rescheduling.
- **Storage breached:** unchanged by this unit.

## Dependencies

None.

## Verify when done

**Technical**
- [ ] `DELETE` on a pending rep returns 204, removes the row, and removes the calendar event
- [ ] `DELETE` on a completed rep returns 409 and the row still exists
- [ ] `DELETE` on a missed rep returns 409 and the row still exists
- [ ] `DELETE` on an unknown UUID still returns 404
- [ ] `DELETE` on a malformed id still returns 422
- [ ] No ✕ renders on completed or missed rows in Today or Week; row alignment is unchanged
- [ ] `npm run lint` passes

**Security**
- [ ] Threat model above run against the implementation
- [ ] The 409 `detail` names only the status, never internal state
- [ ] No new endpoint, no widened surface

**Product**
- [ ] Product invariant 3 ("missed reps stay visible") now holds for every path reachable from the UI
- [ ] Remove the corresponding row from the Known Violations table in `architecture.md`
- [ ] Mark Unit 01 complete in `progress-tracker.md`
