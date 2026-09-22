"""Where the fixture trip sits on the calendar (D55).

``cases/fixture.json`` stores one **template** trip — 2026-11-06 to 2026-11-09,
a Friday to a Monday. The template is not the trip: it is the shape of one, and
the year in it is arithmetic, not a fact. What every repetition actually builds
is that same shape placed on **the next upcoming November**, so a simulated trip
is always in the future. A suite whose fixture quietly slid into the past would
still run, and every reply grounded in "your trip next month" would be answering
about a trip that already happened — wrong in a way no check here looks for.

**The pin preserves the weekday, not the day of the month.** That is the whole
design decision, and it is forced by the cases: seven of them say "Saturday" or
"the Sunday" in the member's own words while their checks name a date, and the
two agree only because 2026-11-07 *is* a Saturday. Roll the year and keep the
6th, and November 2027 makes it a Sunday: every scheduling case would then ask
for one day and assert another, and the suite would report the agent broken.
Keeping the weekday costs the day number instead — the trip is the first Friday
of November, wherever that falls — which is the cheaper loss, because only one
case names a day by its number.

Case files move with it. A case's dates are written against the template, so the
loader shifts every date inside the template's range by the same delta the
fixture moved. Anything outside that range is left alone.

The one thing that cannot be shifted is a date written out in **prose** — "can
you put it on the 9th". ``ordinal_days`` finds those, and the case loader
refuses a case whose prose names a day the trip does not have, so the day this
pin first moves the calendar the suite says which case needs rewording instead
of failing it.
"""

from __future__ import annotations

import copy
import re
from datetime import date, timedelta
from typing import Any

#: The month the fixture trip lives in. November is in the template and the
#: cases are written around it (off-season Lisbon, the wettest month, which is
#: what the weather and packing criteria are scored against).
FIXTURE_MONTH = 11

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
#: "the 9th", "on the 6th" — a day named by number in a member's own words.
_ORDINAL = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b")


def _weekday_slot(day: date) -> tuple[int, int]:
    """(weekday, which occurrence of it in the month) — the pin's coordinates."""
    first = day.replace(day=1)
    first_same = first + timedelta(days=(day.weekday() - first.weekday()) % 7)
    return day.weekday(), (day - first_same).days // 7


def place(template_start: date, year: int) -> date:
    """The template's weekday slot, in ``year``'s November."""
    weekday, occurrence = _weekday_slot(template_start)
    first = date(year, FIXTURE_MONTH, 1)
    first_same = first + timedelta(days=(weekday - first.weekday()) % 7)
    return first_same + timedelta(weeks=occurrence)


def pinned_start(template_start: date, today: date | None = None) -> date:
    """The next upcoming November that still lies ahead of ``today``."""
    today = today or date.today()
    candidate = place(template_start, today.year)
    return candidate if candidate >= today else place(template_start, today.year + 1)


def delta_for(fixture: dict[str, Any], today: date | None = None) -> timedelta:
    template = date.fromisoformat(fixture["trip"]["start_date"])
    return pinned_start(template, today) - template


def template_range(fixture: dict[str, Any]) -> tuple[date, date]:
    return (
        date.fromisoformat(fixture["trip"]["start_date"]),
        date.fromisoformat(fixture["trip"]["end_date"]),
    )


def shift(fixture: dict[str, Any], delta: timedelta) -> dict[str, Any]:
    """The same fixture, every date moved by ``delta``.

    Shape is preserved exactly -- the same stops, the same slots, the same
    offsets between them -- so everything the digest and the checks are written
    against still holds; only the calendar moves. Lives here rather than in
    ``src.fixture`` so the case loader can use it without importing a database
    client it has no need for.
    """
    out = copy.deepcopy(fixture)
    for key in ("start_date", "end_date"):
        out["trip"][key] = (date.fromisoformat(fixture["trip"][key]) + delta).isoformat()
    for slot, original in zip(out["slots"], fixture["slots"]):
        slot["day_date"] = (date.fromisoformat(original["day_date"]) + delta).isoformat()
    return out


def pin(fixture: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """The template trip, placed on the next upcoming November."""
    return shift(fixture, delta_for(fixture, today))


def shift_case_dates(raw: Any, template: tuple[date, date], delta: timedelta) -> Any:
    """Move every date a case wrote against the template by the same delta.

    Applied to the loaded YAML before the case is validated, so a check, an
    anchor and the trip the run builds all name the same day. Bounded to the
    template's own range on purpose: a date outside it is not a reference to a
    trip day and moving it would be a guess.
    """
    if isinstance(raw, dict):
        return {k: shift_case_dates(v, template, delta) for k, v in raw.items()}
    if isinstance(raw, list):
        return [shift_case_dates(v, template, delta) for v in raw]
    if isinstance(raw, str) and _ISO.match(raw):
        try:
            parsed = date.fromisoformat(raw)
        except ValueError:
            return raw
        if template[0] <= parsed <= template[1]:
            return (parsed + delta).isoformat()
    return raw


def ordinal_days(text: str) -> set[int]:
    """Days of the month a piece of prose names by number."""
    return {int(m) for m in _ORDINAL.findall(text or "") if 1 <= int(m) <= 31}
