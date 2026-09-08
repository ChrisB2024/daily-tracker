"""
The chain rule decided 2026-09-07: one empty day forgiven once per chain, length
is the calendar span, today is never judged.

Pure function — no database.
"""

from datetime import date, timedelta

import pytest

from app.services.summary import walk_chain, week_start_for

TODAY = date(2026, 9, 7)


def days(*offsets):
    return {TODAY - timedelta(days=o) for o in offsets}


@pytest.mark.parametrize(
    "offsets, expected, why",
    [
        ((2, 1, 0), 3, "three consecutive days"),
        ((2, 0), 3, "one gap forgiven, span counts the rest day"),
        ((2, 1), 2, "today not done is not a break"),
        ((2,), 1, "grace covers yesterday, today still open"),
        ((3,), 0, "two elapsed empty days ends it"),
        ((4, 2, 0), 3, "a second gap truncates the run at the first"),
        ((), 0, "no completions"),
        ((0,), 1, "only today"),
        ((1,), 1, "only yesterday"),
        (tuple(range(10)), 10, "ten unbroken days"),
        ((0, 1, 4, 5, 6), 2, "a two-day gap always breaks, grace or not"),
        ((-3, 0, 1), 2, "a future-dated completion cannot inflate the chain"),
        ((2, 4), 1, "grace already spent at the head"),
    ],
)
def test_walk_chain(offsets, expected, why):
    assert walk_chain(days(*offsets), TODAY) == expected, why


def test_grace_is_once_per_chain_not_per_gap():
    """Alternate-day work must not sustain a chain indefinitely."""
    alternating = days(0, 2, 4, 6, 8, 10)
    assert walk_chain(alternating, TODAY) == 3  # today, gap, day-2 — then stop


@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2026, 9, 7), date(2026, 9, 7)),   # Monday
        (date(2026, 9, 9), date(2026, 9, 7)),   # Wednesday
        (date(2026, 9, 13), date(2026, 9, 7)),  # Sunday
    ],
)
def test_week_starts_on_monday(day, expected):
    assert week_start_for(day) == expected
