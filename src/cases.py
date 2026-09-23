"""Test cases: the unit of the suite (§3.4, Table 11 test-case level).

A case is one YAML file under ``cases/``. This module is the only place the
shape is defined, so a case a notebook shows, a case the runner executes and a
case the checker evaluates are the same object. Validation errors name the
file and the key: a case that loads is a case that can run.

``declared_constraints`` follows D19 as refined by D27: a ``checks`` mapping of
declarative keys carries everything that can be stated about **one** execution,
and the ``predicates`` list names functions in ``cases/predicates.py`` for the
one thing a schema cannot state — a comparison with **another** execution, which
is what every metamorphic relation is.

A case asserts the **kind** of thing a request implies and not which one
(D32) — a count of places, not a list of venues — with one exception: a place
the **member** named is hers to name. ``slot_moved.block`` and
``draft_reuses_blocks`` are exact for that reason, and they are the only keys
that are.

What a case constrains follows from **what its request asks for**, not from its
function label (D29). An advisory request that asks for advice implies the trip
does not change, so it says so; it does not constrain tools, because a message
carrying no slash command keeps the whole toolset deliberately and whether to
look something up is the agent's judgement.

Every case is written against the fixture trip in ``cases/fixture.json`` (built
and reset by ``src/reset.py``), and ``fixture_depends_on`` names the parts of it
a case assumes — validated here, so a case cannot outlive the state it reads.

``suite_version`` is the SHA-256 over the sorted case files **and the fixture**,
and is what a run records (Table 11): a suite that changed is a different suite,
and so is the same suite against a different starting trip.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
from datetime import date, timedelta
import re
from pathlib import Path
from typing import Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src import calendar_pin

SUBTREE_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = SUBTREE_ROOT / "cases"
REFERENCES_DIR = CASES_DIR / "references"
PREDICATES_FILE = CASES_DIR / "predicates.py"
FIXTURE_FILE = CASES_DIR / "fixture.json"

Function = Literal["venue_lookup", "scheduling", "factual_qa", "advisory"]
Provenance = Literal["seeded", "metamorphic", "retained"]
Intent = Literal["find", "plan", "reschedule"]

#: Tools that read the trip's own state and write nothing. Never a violation
#: under deny-by-default (D28): the agent calls them only when its preloaded
#: prompt context is not enough, which varies between runs of one case, so
#: treating them as unexpected would fail a case on variance rather than on a
#: regression. Mirrors READ_TOOLS in apps/api/src/routes/ai/agent/agent.tool-policy.ts.
#: Every tool the agent has, mirrored from apps/api/src/routes/ai/agent/
#: (agent.tools.ts and agent.itinerary-tools.ts). Mirrored rather than
#: imported, for the reason the API mirrors the shared package: this subtree
#: cannot resolve a TypeScript module. The loader checks a case's tool names
#: against it — keep both in sync.
ALL_TOOL_NAMES = frozenset({
    "get_trip_details",
    "list_trip_blocks",
    "get_itinerary",
    "search_places",
    "get_weather",
    "get_climate_normals",
    "get_region_climate",
    "read_wikipedia",
    "propose_plan",
    "move_slot",
    "unschedule_block",
    "schedule_block",
})

ALWAYS_ALLOWED_TOOLS = ("get_trip_details", "list_trip_blocks", "get_itinerary")

#: The tables the mutation triggers watch (D13). A ``mutation_counts`` or
#: ``mutation_changed_keys`` key names one of these and an operation: a
#: misspelled table is a count of rows that can never exist, which passes a
#: zero and fails a minimum, silently, forever.
MUTATION_TABLES = frozenset({
    "trip_blocks",
    "itinerary_slots",
    "itinerary_days",
    "ai_suggestions",
    "branches",
})
MUTATION_OPS = frozenset({"INSERT", "UPDATE", "DELETE"})

#: The D22 catalogue. A follow-up case names exactly one.
METAMORPHIC_RELATIONS = (
    "INV-1", "INV-2", "INV-3", "INV-4",
    "DIR-1", "DIR-2", "DIR-3", "DIR-4",
)


class Bound(BaseModel):
    """An integer requirement: exact, or a closed range."""

    model_config = ConfigDict(extra="forbid")
    min: Optional[int] = None
    max: Optional[int] = None

    def holds(self, n: int) -> bool:
        return (self.min is None or n >= self.min) and (self.max is None or n <= self.max)


BoundLike = Union[int, Bound]


def as_bound(value: BoundLike) -> Bound:
    return Bound(min=value, max=value) if isinstance(value, int) else value


TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def minutes_of(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


class SlotMoved(BaseModel):
    """One stop ends up on one day, inside a window, at roughly its length.

    A member names a time the way people do — "around 4", "Saturday
    afternoon" — so the case asserts the range those words mean and not a clock
    reading (D31). Two things make an exact time the wrong assertion. The words
    themselves are a range: an agent that writes 16:15 for "around 4" has
    understood the request. And the day may already hold something near the
    target, in which case shifting away from the exact minute is the correct
    behaviour, not a miss — so a case whose target day is busy widens the
    window to the part of the day the member named and asserts
    ``clear_of_other_slots`` instead of a narrow one.

    Length is asserted separately, because the two failures are different: an
    agent that lands the start correctly and leaves the stored end where it was
    turns an hour-long stop into one that runs to the end of the day, and no
    assertion about the start would notice.
    """

    model_config = ConfigDict(extra="forbid")
    #: The stop's title, as the fixture and the trip call it.
    block: str
    #: YYYY-MM-DD. A day is what the member named and carries no tolerance:
    #: "Saturday" is one day, and an agent on the wrong one is wrong.
    day: str
    #: Inclusive ``[earliest, latest]`` HH:MM range the start must fall in.
    #: Omit where the case asks for a day and not a time. A case that means an
    #: exact minute writes the same value twice, so the tolerance it intends is
    #: always visible rather than implied by the absence of one.
    starts_between: Optional[tuple[str, str]] = None
    #: How long the stop runs afterwards, in minutes, exact or bounded. Where
    #: the case means "unchanged", the bound brackets the length the fixture
    #: gives that slot — stated, because a case that silently inherits it
    #: cannot say whether a changed fixture changed what it tests.
    duration_minutes: Optional[BoundLike] = None
    #: The stop does not overlap another slot on that day. The assertion for a
    #: day with something already on it, where the exact landing time is the
    #: agent's to choose and the requirement is that it chose a free window.
    clear_of_other_slots: Optional[bool] = None

    @model_validator(mode="after")
    def _window_is_a_window(self) -> "SlotMoved":
        if self.starts_between is None:
            return self
        earliest, latest = self.starts_between
        for value in (earliest, latest):
            if not TIME_RE.match(value):
                raise ValueError(f"starts_between takes HH:MM times, got {value!r}")
        if minutes_of(earliest) > minutes_of(latest):
            raise ValueError(
                f"starts_between must read earliest first, got {earliest} to {latest}"
            )
        return self


class EditCounts(BaseModel):
    """Live itinerary edits the agent journalled this execution (D10's
    ``resulting_state_shape.edits``), summed across its turns.

    The agent's own account of what it did, beside ``mutation_counts``, which
    is the database's. Both are kept because they fail differently: an edit
    journalled but not written, or written but not journalled, is a fault
    either way and neither signal alone sees it.
    """

    model_config = ConfigDict(extra="forbid")
    move: Optional[BoundLike] = None
    unschedule: Optional[BoundLike] = None
    schedule: Optional[BoundLike] = None


#: ``trip_after`` counts may be written as the fixture's own, so the case says
#: what it means — "as many stops as we started with" — rather than a number
#: that silently stops matching when the fixture changes.
FIXTURE_COUNT = "fixture"
CountLike = Union[int, Bound, Literal["fixture"]]


class TripAfter(BaseModel):
    """How much trip there is when the execution ends
    (``resulting_state_shape.trip_after`` of the last turn, D10).

    The positive form of "nothing was written". ``mutation_counts`` says no
    row was recorded; this says the trip is the size it was, which is the same
    claim from the other side and does not depend on the mutation trigger
    having fired. A read-only case wants both.
    """

    model_config = ConfigDict(extra="forbid")
    #: Stops on the trip afterwards. ``fixture`` means the fixture's own count.
    blocks: Optional[CountLike] = None
    #: Scheduled slots afterwards. ``fixture`` means the fixture's own count.
    slots: Optional[CountLike] = None


class PlacesNear(BaseModel):
    """Every place the reply names sits within ``within_km`` of a fixture stop.

    The geographic sanity check, and the one a venue set cannot fake. "Different
    venues from the seed" is satisfied by two *different Sintra* restaurants
    when the member asked about Lisbon; only distance says the agent answered
    about the right place.

    The anchor is a **fixture stop title**, not a pair of coordinates, for the
    same reason ``slot_moved.block`` is: the fixture already knows where its
    stops are, the loader can check the name, and a case that typed its own
    latitude would drift the first time the fixture moved.

    ``within_km`` is the member's words rendered as a distance, the way D31
    renders "around 4" as a window — "near the palace" is the Sintra area,
    "near the hotel in Baixa" is central Lisbon. It is deliberately **not**
    the application's own ``VENUE_SANITY_KM`` of 300, which exists to catch
    Lisbon-versus-Porto and would pass every answer this check exists to fail:
    Pena Palace and Baixa are 23 km apart.
    """

    model_config = ConfigDict(extra="forbid")
    #: A stop title from cases/fixture.json; its coordinates are the centre.
    anchor: str
    within_km: float = Field(gt=0)


class SlotScheduled(BaseModel):
    """A stop the trip already had ends up ON the itinerary, on a day, in a
    window.

    The counterpart of ``slot_moved`` for a stop that was saved and unscheduled.
    It exists because the one case that exercises ``schedule_block`` asserted
    only that the tool ran: an agent that put the monastery on the wrong day at
    the wrong hour satisfied every other check, since the write is an INSERT and
    ``slot_moved`` reads UPDATE rows. Verifying that a tool ran is not
    verifying that it did what was asked.

    Read off the ``itinerary_slots.INSERT`` mutation's projection, which
    carries the resolved ``day_date`` alongside the times.
    """

    model_config = ConfigDict(extra="forbid")
    #: The stop's title, as the fixture and the trip call it.
    block: str
    #: YYYY-MM-DD. A day carries no tolerance: the member named one.
    day: str
    #: Inclusive ``[earliest, latest]`` HH:MM range the start must fall in —
    #: the member's words, not a clock reading (D31).
    starts_between: Optional[tuple[str, str]] = None
    duration_minutes: Optional[BoundLike] = None

    @model_validator(mode="after")
    def _window_is_a_window(self) -> "SlotScheduled":
        if self.starts_between is None:
            return self
        earliest, latest = self.starts_between
        for value in (earliest, latest):
            if not TIME_RE.match(value):
                raise ValueError(f"starts_between takes HH:MM times, got {value!r}")
        if minutes_of(earliest) > minutes_of(latest):
            raise ValueError(f"starts_between must read earliest first, got {earliest} to {latest}")
        return self


class SlotUnscheduled(BaseModel):
    """A named stop comes OFF the itinerary, and stays saved in the trip.

    Without it the negation case asserted only that something was unscheduled:
    an agent that took the Time Out Market lunch off instead of the tram ride
    satisfied every check it declared — the tool ran, one slot fewer, the same
    number of stops — and the verdict read `none`. Its sibling names its stop
    through ``slot_scheduled``; the negation had no counterpart, and a check
    that passes an incorrect agent is the quieter of D30's two errors and the
    worse one.

    Read off the ``itinerary_slots.DELETE`` mutation's projection, which
    carries ``trip_block_id``.
    """

    model_config = ConfigDict(extra="forbid")
    #: The stop's title, as the fixture and the trip call it.
    block: str


class Checks(BaseModel):
    """What a case asserts about an execution, declaratively (D19, D27).

    Every key is optional and an absent key is not a constraint. The checker
    (B08) knows exactly these; a case cannot invent one, because a constraint
    nothing evaluates is worse than no constraint.

    **Where a new key comes from (D37).** The vocabulary is derived from
    ``docs/event-model.md``: a key exists because the application already
    records the field it reads, and the docstring of each one names that
    field. It was not derived that way originally, and two keys were found by
    accident as a result (Q21). The rule that replaces the accident has two
    halves — a candidate key is found by reading the event model, and it is
    added when a case needs it, so that every key in this class is exercised
    by at least one case. A key nobody asserts is a key nobody validates.

    **What is recorded but deliberately not assertable.** ``reply.chars``,
    ``latency_ms``, the token counts, ``llm_calls`` and ``tool_calls`` are
    carried on every execution and reported per case by the checker, but no
    case may bound them: there is no baseline yet to bound them against, and a
    window invented before the first run is a threshold nobody can defend
    (Q22, deferred to B10). ``request_type`` and ``agent_intent`` are the
    participant round's labels and B12's signature field, not a case's
    assertion.
    """

    model_config = ConfigDict(extra="forbid")

    # --- what the agent called ---
    #: Calls per tool, exact or bounded. Under D28 a zero is never needed: a
    #: tool the case does not name is already forbidden.
    tool_counts: Optional[dict[str, BoundLike]] = None
    #: At least one of these ran **and came back with something** — no error,
    #: and not a miss. The claim is "answered from a source", and a source
    #: that failed or found nothing answered nothing. Two ways that was too
    #: weak before: requiring only that the call happened let a failed climate
    #: lookup followed by a successful forecast satisfy the weather case; and
    #: the reference tools signal a miss with ``found: false`` and no
    #: ``error`` key, so a lookup that matched no article counted as a source
    #: until the checker was told otherwise.
    tools_any_of: Optional[list[str]] = None
    #: How tool errors (D11's tool-level failure) are treated (D33).
    #:
    #: ``"none"``      no tool returned or threw an error.
    #: ``"corrected"`` an error is permitted only where the agent recovers
    #:                 from **that** error, in one of two ways. Either a later
    #:                 call to the tool that failed, or to one named in
    #:                 ``tools_any_of``, succeeds — or the failure was a
    #:                 **probe** and the agent abandoned it: a tool this case
    #:                 permits at ``min: 0``, names in no other check, and
    #:                 whose result nothing depends on. Walking away from a
    #:                 source that could not answer is a recovery, and it is
    #:                 often the only one available, because a probe is capped
    #:                 at one call and so cannot be retried. An error that is
    #:                 neither retried nor abandoned fails.
    #:
    #:                 The narrowing to "that error" matters: at "any tool this
    #:                 case names" a failed climate lookup was corrected by a
    #:                 successful forecast call, which answers a different
    #:                 question.
    #: absent          tool errors are not constrained at all.
    #:
    #: ``"corrected"`` is what a case writes when the application legitimately
    #: refuses a reasonable first attempt, or when a tool the agent may
    #: sensibly try cannot answer the question it was tried for. Both happen,
    #: and an agent that notices and switches is behaving well (D30).
    tool_errors: Optional[Literal["none", "corrected"]] = None
    #: ``"none"``: no turn of this execution ended with a
    #: ``study_suggestions.error_code`` (D11's closed set — ``timeout |
    #: llm_call_limit | empty_reply | llm_error | persist_failed | other``).
    #:
    #: The turn-level counterpart of ``tool_errors``, and the one that catches
    #: a failure nothing else does: ``empty_reply`` returns HTTP 200, so the
    #: simulator reads a blank reply, answers it in character and the case
    #: goes on to pass every check about a trip that was never touched. A
    #: read-only case is exactly where that is invisible.
    turn_errors: Optional[Literal["none"]] = None

    # --- what it surfaced ---
    #: Places ``search_places`` returned across the turn, bounded. This counts
    #: the search's own results and NOT what the reply did with them: a search
    #: whose results the agent never mentions still satisfies it. Use it to say
    #: "it actually searched", and use ``places_named`` for "it actually
    #: answered".
    places_surfaced: Optional[BoundLike] = None
    #: Places the reply itself referenced (``resulting_state_shape.reply
    #: .place_refs``), bounded. This is the venue-lookup assertion that bites:
    #: a reply naming nothing passes every other check a read-only case has.
    places_named: Optional[BoundLike] = None
    #: The reply names at least one place of **each** of these Google place
    #: types (``chat_messages.metadata.refs[].placeType``, e.g. ``restaurant``,
    #: ``lodging``). Matched loosely, because Google's primary type for a hotel
    #: is sometimes ``lodging`` and sometimes ``hotel``.
    #:
    #: For a request that asks for two different kinds of thing at once — "a
    #: seafood place and somewhere to stay nearby" — where a count cannot tell
    #: the difference between five restaurants and a restaurant plus a hotel.
    #: `search_places` is capped at five results per call, so narrowing a
    #: request never *reduces* what it surfaces; asking for a second kind of
    #: place is the perturbation that actually changes the shape of the answer.
    places_named_types: Optional[list[str]] = None
    #: No place the reply names is of these kinds — a NEGATIVE type assertion,
    #: for a request that says what it does not want (D72).
    #:
    #: The positive form cannot express "somewhere to get a drink". Google's
    #: primary type for a riverside bar is `cocktail_bar` on one run and
    #: `restaurant` on the next, so asserting `['bar']` measured Google's
    #: taxonomy rather than the agent — it failed executions where the agent
    #: had searched `waterfront bar Cais do Sodre` and returned three correct
    #: rooftop bars, and the judge scored those 9 and 10 out of 10.
    #:
    #: The negation is robust because it does not depend on how a drink place
    #: is typed, only on the answer not being the one the perturbation ruled
    #: out. Measured over the recorded runs: the seafood seed named a
    #: `seafood_*` venue in 10 of 13 executions, its "not a meal" follow-up in
    #: 0 of 5. That is the delta DIR-4 claims, stated so that Google's
    #: inconsistency cannot manufacture a false regression (D30).
    #: `placeType` is Google's `primaryType` passed through verbatim
    #: (`agent.tools.ts`), so these are Google's own strings and not ours.
    #:
    #: Its limit, stated because it is the same dependence on that taxonomy
    #: pointed the safer way: `primaryType` is ONE string, and Google types
    #: some seafood places plain `restaurant` — which is why the seed carries a
    #: `seafood_*` type in 10 of 13 executions and not 13. A regressed agent
    #: whose seafood venues all happened to be typed `restaurant` would slip
    #: through. It fails OPEN rather than closed, which is the direction D30
    #: asks for: a missed regression costs a finding, a false one costs trust.
    places_excluded_types: Optional[list[str]] = None
    #: Every place the reply names is within a radius of a fixture stop — the
    #: check that says the agent answered about the right *place*, which a
    #: venue count and a venue-set comparison both miss.
    places_near: Optional[PlacesNear] = None

    # --- the draft it proposed ---
    #
    # These read the arguments of the LATEST ``propose_plan`` call, recorded
    # verbatim in ``study_suggestions.tool_call_trace``. Not
    # ``resulting_state_shape.draft``, which carries counts only — how many
    # days, how many slots, which block types — and no dates or times at all:
    # pointing a checker there would have left ``slot_days`` unevaluable and a
    # Belem morning drafted onto the Sintra day passing every check.
    #
    # Latest call, so a case that permits a revision has a defined target: the
    # plan the member was left with, not whichever of two rows a checker
    # happened to pick up.
    #
    #: Every draft slot's day must be one of these (YYYY-MM-DD).
    slot_days: Optional[list[str]] = None
    #: Number of slots the draft holds.
    slot_count: Optional[BoundLike] = None
    #: Every draft slot starts inside this inclusive ``[earliest, latest]``
    #: HH:MM window. A member who asks for a morning is asking about the
    #: hours, and without this a draft of an afternoon described as a morning
    #: passes: the drafting tool instructs the reply not to repeat every slot,
    #: so the reply usually names no time and a criterion about the times it
    #: names is vacuous exactly when it is needed. Same window rule as
    #: ``slot_moved.starts_between`` (D31) — the member's words, not a clock
    #: reading.
    draft_slot_starts_between: Optional[tuple[str, str]] = None
    #: Stops the draft must be built on, by title. Satisfied when a slot's
    #: ``reuse_block_id`` argument resolves to that stop through the ids the
    #: rebuild produced for this execution (D26), **or** when a slot's own
    #: title would resolve to it the way the application does: case-folded,
    #: either title containing the other, which is how ``matchExistingVenue``
    #: attaches a saved venue when the model names it without passing the id.
    #: The mirroring is deliberate — an agent that honours the member's "we
    #: already have it" by title has honoured it, and failing that would be a
    #: false regression.
    #:
    #: This is D32's exception, and the exception is about **who named the
    #: place**. A case never says which restaurant or which monument the agent
    #: should find — that is the agent's judgement and the author's taste is
    #: not a pass criterion. But a place the member herself named is hers, not
    #: the author's: "we already have the monastery saved" is an instruction,
    #: and a draft that ignores the saved stop and finds its own has answered a
    #: different request. The other half of the exception is
    #: ``slot_moved.block``, where the member pointed at a stop to move.
    draft_reuses_blocks: Optional[list[str]] = None

    # --- what it changed on the live itinerary ---
    #: A named stop ends up in a named window.
    slot_moved: Optional[SlotMoved] = None
    #: A named stop ends up scheduled on a named day, in a window.
    slot_scheduled: Optional[SlotScheduled] = None
    #: A named stop comes off the itinerary and stays saved in the trip.
    slot_unscheduled: Optional[SlotUnscheduled] = None
    #: The agent's own journal of its live edits, summed over the execution.
    edits: Optional[EditCounts] = None

    # --- what the database recorded ---
    #: study_mutations rows per (table, op) — e.g. ``itinerary_slots.INSERT: 1``.
    mutation_counts: Optional[dict[str, BoundLike]] = None
    #: Which columns a write was allowed to touch, per ``table.OP`` — the
    #: ``changed_keys`` array the mutation trigger records (UPDATE only; an
    #: INSERT has no meaningful one). Read as deny by default over columns,
    #: the way D28 reads tools: **every** row of that table and op must have
    #: changed only keys drawn from this list, and a key in the list that
    #: nothing changed is not a failure. That is what states "the move changed
    #: the day and the times and nothing else" — the part that was previously
    #: unsayable, and the part that catches a move which also quietly cleared
    #: a lock, a precision or a block link.
    mutation_changed_keys: Optional[dict[str, list[str]]] = None

    # --- how much trip there is afterwards ---
    trip_after: Optional[TripAfter] = None


    @model_validator(mode="after")
    def _mutation_keys_name_a_table_and_an_op(self) -> "Checks":
        for field, mapping in (
            ("mutation_counts", self.mutation_counts),
            ("mutation_changed_keys", self.mutation_changed_keys),
        ):
            for key in mapping or {}:
                table, _, op = key.partition(".")
                if table not in MUTATION_TABLES or op not in MUTATION_OPS:
                    raise ValueError(
                        f"{field} key {key!r} must read <table>.<OP> — table one of "
                        f"{', '.join(sorted(MUTATION_TABLES))}, OP one of "
                        f"{', '.join(sorted(MUTATION_OPS))}"
                    )
                if field == "mutation_changed_keys" and op != "UPDATE":
                    raise ValueError(
                        f"mutation_changed_keys key {key!r}: only an UPDATE has changed keys — "
                        f"the trigger records them for UPDATE alone. Use mutation_counts for "
                        f"{op}."
                    )
        return self

    @model_validator(mode="after")
    def _draft_window_is_a_window(self) -> "Checks":
        if self.draft_slot_starts_between is None:
            return self
        earliest, latest = self.draft_slot_starts_between
        for value in (earliest, latest):
            if not TIME_RE.match(value):
                raise ValueError(
                    f"draft_slot_starts_between takes HH:MM times, got {value!r}"
                )
        if minutes_of(earliest) > minutes_of(latest):
            raise ValueError(
                f"draft_slot_starts_between must read earliest first, got {earliest} to {latest}"
            )
        return self


class Constraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checks: Checks = Field(default_factory=Checks)
    #: Names of functions in cases/predicates.py — the comparisons with another
    #: execution, which no schema key can state (D27).
    predicates: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return self.checks == Checks() and not self.predicates


class Reference(BaseModel):
    """A stored source a factual-QA answer is judged against (D23)."""

    model_config = ConfigDict(extra="forbid")
    title: str
    section: Optional[str] = None
    #: File under cases/references/ holding the stored text.
    path: str

    def text(self) -> str:
        return (REFERENCES_DIR / self.path).read_text(encoding="utf-8")


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    base_case_id: Optional[str] = None
    provenance: Provenance
    run_priority: int = Field(ge=1)
    function: Function
    user_profile: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    opening_turn: str = Field(min_length=1)
    #: The slash command the simulator opens with, if the case says so.
    intent: Optional[Intent] = None
    #: The tools the case expects, in order (Table 11). This is the ordering
    #: constraint itself, not a description of one: the checker requires them
    #: to appear in the trace in this order, as a subsequence, so a case that
    #: expects a grounded plan writes [search_places, propose_plan] and gets
    #: both the presence and the order from one field. Empty constrains nothing.
    expected_tool_sequence: list[str] = Field(default_factory=list)
    declared_constraints: Constraints = Field(default_factory=Constraints)
    #: The point-wise rubric, one criterion per line, scored 1..10 (§3.1).
    scoring_criteria: list[str] = Field(min_length=1)
    references: list[Reference] = Field(default_factory=list)
    repetitions_n: int = Field(ge=1)
    metamorphic_relation: Optional[str] = None
    #: What the case leans on in the fixture trip: stop titles from
    #: cases/fixture.json and/or day dates inside the trip's range. The loader
    #: checks them, so a case cannot quietly outlive the state it assumes —
    #: "move the Tram 28 ride" is only a case while that stop is in the
    #: fixture. Empty means the case reads nothing off the trip.
    fixture_depends_on: list[str] = Field(default_factory=list)
    #: Which calendar the fixture trip sits on (D54). ``fixture`` is the fixed
    #: November trip every other case uses, and a stable calendar is most of
    #: what makes a criterion like "the Sunday" checkable. ``near`` moves the
    #: same trip to start a few days from the run, which exactly one kind of
    #: case needs: a forecast is only obtainable within sixteen days of being
    #: asked for, so no fixed date can test the during-the-trip path and still
    #: be inside the window next month.
    fixture_dates: Literal["fixture", "near"] = "fixture"
    #: Free text for the notebook: why this case exists, what it exercises.
    notes: Optional[str] = None

    def constrains_tools(self) -> bool:
        """True when the case says anything about which tools may run. A case
        that says nothing constrains nothing (D28): that is how the advisory
        seeds stay free to ground their advice."""
        checks = self.declared_constraints.checks
        return bool(self.expected_tool_sequence or checks.tool_counts or checks.tools_any_of)

    def allowed_tools(self) -> Optional[set[str]]:
        """Every tool this case permits, or None when it constrains none.

        Deny by default (D28): the union of what the case names, plus the read
        tools, and any other call is a structural failure. Listing what a case
        expects is therefore the whole of its tool constraint — there are no
        zeros to write, and a tool nobody thought to forbid is forbidden
        anyway, which is the point.
        """
        if not self.constrains_tools():
            return None
        checks = self.declared_constraints.checks
        allowed = set(ALWAYS_ALLOWED_TOOLS) | set(self.expected_tool_sequence)
        allowed |= set(checks.tool_counts or {})
        allowed |= set(checks.tools_any_of or [])
        # A tool bounded at zero is named in order to be forbidden, not allowed.
        for tool, bound in (checks.tool_counts or {}).items():
            if as_bound(bound).max == 0:
                allowed.discard(tool)
        return allowed

    def named_fixture_stops(self) -> list[str]:
        """Stop titles this case names anywhere — for the loader's check that
        a case cannot outlive the state it reads."""
        checks = self.declared_constraints.checks
        named = list(checks.draft_reuses_blocks or [])
        if checks.slot_moved:
            named.append(checks.slot_moved.block)
        if checks.slot_scheduled:
            named.append(checks.slot_scheduled.block)
        if checks.slot_unscheduled:
            named.append(checks.slot_unscheduled.block)
        if checks.places_near:
            named.append(checks.places_near.anchor)
        return named

    @model_validator(mode="after")
    def _coherent(self) -> "Case":
        if self.provenance == "metamorphic":
            if not self.base_case_id:
                raise ValueError("a metamorphic case needs base_case_id")
            if self.metamorphic_relation not in METAMORPHIC_RELATIONS:
                raise ValueError(
                    f"metamorphic_relation must be one of {', '.join(METAMORPHIC_RELATIONS)}"
                )
        elif self.metamorphic_relation is not None:
            raise ValueError("only a metamorphic case carries metamorphic_relation")
        if self.function == "factual_qa" and not self.references:
            raise ValueError("a factual_qa case needs at least one reference")
        if self.function == "advisory" and self.constrains_tools():
            raise ValueError(
                "an advisory case does not constrain tools: it carries no slash command, so the "
                "agent keeps its whole toolset and whether to look anything up is its call (D29). "
                "Constrain what the request implies about the trip instead."
            )
        return self


_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


class CaseFileError(ValueError):
    """A case file that cannot be loaded, naming the file and what is wrong."""


def fixture() -> dict:
    """The trip every repetition starts from (cases/fixture.json, built by B02).

    Pinned to the next upcoming November (D55), the same way ``src.fixture``
    pins it — two loaders on two calendars would disagree about which day an
    anchor names, and the disagreement would surface as a gate failure.
    """
    return calendar_pin.pin(json.loads(FIXTURE_FILE.read_text(encoding="utf-8")))


def _trip_day_dates() -> list[str]:
    data = fixture()
    start = date.fromisoformat(data["trip"]["start_date"])
    end = date.fromisoformat(data["trip"]["end_date"])
    out, day = [], start
    while day <= end:
        out.append(day.isoformat())
        day += timedelta(days=1)
    return out


def fixture_anchors(data: Optional[dict] = None) -> set[str]:
    """What a case may declare a dependency on: stop titles and trip days.

    Titles, not an alias invented for the fixture file: a stop is called the
    same thing here, in the trip the harness builds, in a ``study_mutations``
    projection and in the case's own opening turn. One vocabulary means a
    declaration can be checked against the case's prose, and a reader of a
    failed run does not have to translate.
    """
    data = data or fixture()
    anchors = {block["title"] for block in data["blocks"]}
    start = date.fromisoformat(data["trip"]["start_date"])
    end = date.fromisoformat(data["trip"]["end_date"])
    day = start
    while day <= end:
        anchors.add(day.isoformat())
        day += timedelta(days=1)
    return anchors


def fixture_counts(data: Optional[dict] = None) -> dict[str, int]:
    """How much trip the fixture is — what ``trip_after: fixture`` resolves to.

    One definition, used by the checker and by the notebook, so "as many stops
    as we started with" cannot mean two things.
    """
    data = data or fixture()
    return {"blocks": len(data["blocks"]), "slots": len(data["slots"])}


def _predicate_names() -> set[str]:
    if not PREDICATES_FILE.exists():
        return set()
    spec = importlib.util.spec_from_file_location("study_predicates", PREDICATES_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    # Functions DEFINED there, not everything callable in its namespace: the
    # module imports Mapping and Optional, and a case naming one of those as a
    # predicate would have passed validation and then failed at check time.
    return {
        name
        for name, value in vars(module).items()
        if inspect.isfunction(value) and value.__module__ == module.__name__ and not name.startswith("_")
    }


def case_files(directory: Path = CASES_DIR) -> list[Path]:
    """Every case file, sorted by name. Underscore-prefixed files are drafts."""
    return sorted(p for p in directory.glob("*.yaml") if not p.name.startswith("_"))


def load_case(
    path: Path,
    known_predicates: Optional[set[str]] = None,
    known_anchors: Optional[set[str]] = None,
) -> Case:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CaseFileError(f"{path.name}: not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise CaseFileError(f"{path.name}: expected a mapping at the top level")
    # Case files are written against the template calendar in the fixture file;
    # the trip is built on the pinned one (D55). Shift the dates here, once, so
    # every consumer downstream — checks, anchors, the checker's slot windows —
    # sees the calendar the run actually used.
    template = json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))
    raw = calendar_pin.shift_case_dates(
        raw, calendar_pin.template_range(template), calendar_pin.delta_for(template)
    )
    try:
        case = Case.model_validate(raw)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or '(root)'}: {e['msg']}" for e in exc.errors()
        )
        raise CaseFileError(f"{path.name}: {problems}") from exc
    if case.case_id != path.stem:
        raise CaseFileError(f"{path.name}: case_id {case.case_id!r} must equal the file name")
    known = _predicate_names() if known_predicates is None else known_predicates
    unknown = [p for p in case.declared_constraints.predicates if p not in known]
    if unknown:
        raise CaseFileError(f"{path.name}: unknown predicate(s) {unknown} — define them in cases/predicates.py")
    for ref in case.references:
        if not (REFERENCES_DIR / ref.path).exists():
            raise CaseFileError(f"{path.name}: reference file missing: references/{ref.path}")
    # A near-dated case's trip is on a different calendar every run, so a day
    # anchor on it would be checked here against November and built against
    # next week — true at load and false in the trip. Titles still hold: the
    # shift moves dates and nothing else.
    if case.fixture_dates == "near":
        dated = [a for a in case.fixture_depends_on if _DAY.fullmatch(a)]
        if dated:
            raise CaseFileError(
                f"{path.name}: fixture_dates 'near' cannot depend on the day(s) {dated} — a near-dated "
                f"trip is on a different calendar every run; depend on stop titles instead"
            )
    # A date written out in prose ("put it on the 9th") is not a field and
    # cannot be shifted with the rest. When the pin moves the calendar, such a
    # case asks for a day the trip no longer has — and would fail as an agent
    # fault. Refuse it by name instead, so the fix is obvious.
    if case.fixture_dates == "fixture":
        trip_days = {date.fromisoformat(d).day for d in _trip_day_dates()}
        named = calendar_pin.ordinal_days(case.opening_turn)
        stray = sorted(named - trip_days)
        if stray:
            raise CaseFileError(
                f"{path.name}: opening_turn names day(s) {stray} of the month, but the trip runs "
                f"{sorted(trip_days)}. The fixture is pinned to the next upcoming November (D55) and "
                f"the day numbers moved; reword the turn, or name the weekday instead"
            )
    anchors = fixture_anchors() if known_anchors is None else known_anchors
    unknown_anchors = [a for a in case.fixture_depends_on if a not in anchors]
    if unknown_anchors:
        raise CaseFileError(
            f"{path.name}: fixture_depends_on names {unknown_anchors}, which the fixture does not "
            f"have — a stop title from cases/fixture.json or a day inside the trip's range"
        )
    # A misspelled tool is worse than a missing one: it is permitted (D28) and
    # never called, and in tools_any_of it is a requirement nothing can meet.
    named_tools = set(case.expected_tool_sequence)
    named_tools |= set(case.declared_constraints.checks.tool_counts or {})
    named_tools |= set(case.declared_constraints.checks.tools_any_of or [])
    unknown_tools = sorted(named_tools - ALL_TOOL_NAMES)
    if unknown_tools:
        raise CaseFileError(
            f"{path.name}: names tool(s) {unknown_tools} the agent does not have — "
            f"see ALL_TOOL_NAMES, mirrored from apps/api/src/routes/ai/agent/"
        )
    # The two keys that name a place (D32) draw from the same vocabulary, so a
    # renamed stop fails here rather than becoming a check nothing can satisfy.
    unknown_stops = [t for t in case.named_fixture_stops() if t not in anchors]
    if unknown_stops:
        raise CaseFileError(
            f"{path.name}: names stop(s) {unknown_stops} the fixture does not have — "
            f"slot_moved.block and draft_reuses_blocks take a title from cases/fixture.json"
        )
    return case


def load_cases(directory: Path = CASES_DIR) -> list[Case]:
    """Every case, validated, with base cases checked to exist."""
    known = _predicate_names()
    anchors = fixture_anchors()
    cases = [load_case(path, known, anchors) for path in case_files(directory)]
    ids = {c.case_id for c in cases}
    for c in cases:
        if c.base_case_id and c.base_case_id not in ids:
            raise CaseFileError(f"{c.case_id}.yaml: base_case_id {c.base_case_id!r} is not a case")
    return cases


def suite_version(directory: Path = CASES_DIR, today: Optional[date] = None) -> str:
    """SHA-256 over the sorted case files and the fixture they run against.

    The fixture is in the hash on purpose: the same case text against a
    different starting trip is a different test, and Table 11's suite version
    has to say so.

    **The fixture is hashed as RESOLVED, not as stored (D62).** Since D55 the
    file holds a template and the trip actually built is that template pinned
    to the next upcoming November, so hashing the file's bytes would give two
    runs on two different calendars the same suite version — the exact case
    this hash exists to distinguish, and the one its own docstring promised to
    catch. Hashing what gets built keeps the promise: the version moves when
    the calendar does, because that genuinely is a different starting trip.

    One case is deliberately outside this. `fixture_dates: near` (D54) builds a
    trip relative to the run, so folding it in would change the suite version
    every day and make two runs in one week incomparable for no gain. The hash
    therefore identifies the fixed calendar every other case shares; that one
    case's calendar is recoverable from its own trip row.
    """
    digest = hashlib.sha256()
    fixture_path = directory / "fixture.json"
    if fixture_path.exists():
        resolved = calendar_pin.pin(json.loads(fixture_path.read_text(encoding="utf-8")), today)
        digest.update(b"fixture.json\0")
        digest.update(json.dumps(resolved, sort_keys=True).encode("utf-8"))
        digest.update(b"\0")
    for path in case_files(directory):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def by_priority(cases: list[Case]) -> list[Case]:
    """P7: run order — priority first, seeds before their follow-ups, then name."""
    return sorted(cases, key=lambda c: (c.run_priority, c.provenance != "seeded", c.case_id))


def case_version(case_id: str, directory: Path = CASES_DIR) -> str:
    """This case's version: the first 12 hex of a hash of its file (D74).

    Derived, not declared. A hand-maintained version number is a number nobody
    bumps — the two `package.json` versions in this repo sat at their scaffold
    defaults for 377 commits, which is the same lesson from the other side of
    the fence. A content hash cannot drift from the thing it names.

    What it buys: a review mark can say WHICH text was approved, and an
    execution can say which version of the case produced it. `suite_version`
    already covers the suite as a whole; this is the per-case resolution the
    aggregate cannot give. A case edited after it was marked (D48 added a
    check to both venue seeds, D55 moved the calendar, D58 raised a cap, D72
    inverted the drinks assertion) is then visible as drift rather than
    silently carrying an approval for text that no longer exists.
    """
    return _case_content_sha(directory / f"{case_id}.yaml")


def _case_content_sha(path: Path) -> str:
    """Hash of a case file, for binding a review mark to what was reviewed."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else ""


def mark_reviewed(case_id: str, by: str = "author", directory: Path = CASES_DIR) -> dict:
    """Record the author's review of a case, bound to the text reviewed.

    **For the author to call, never the agent.** `reviewed.json` says the mark
    "is what makes a seed the author's rather than the model's (3.1)", so an
    agent writing one would be forging the provenance the study rests on. This
    function exists so that when the author does mark a case, the mark carries
    a version and the next edit shows as drift instead of passing unnoticed.
    """
    import datetime

    path = directory / "reviewed.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = {
        "by": by,
        "on": datetime.date.today().isoformat(),
        "sha": case_version(case_id, directory),
    }
    data.setdefault("reviewed", {})[case_id] = entry
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return entry


def review_status(directory: Path = CASES_DIR) -> dict[str, dict]:
    """Which seeds carry the author's mark, and whether it still binds.

    Two separate questions, and the file answered only the first. A mark is
    ``{by, on}`` — it records that the author read the case on a date, not
    WHICH text they read. Every marked seed has been edited since (D48 added
    `places_near` to both venue seeds, D55 moved the fixture's calendar, D58
    raised a cap), so "reviewed" was quietly doing less work than it looked
    like.

    New marks may carry ``sha``; old ones do not, and are reported as
    ``unverifiable`` rather than as verified or as drifted. Nothing here writes
    a mark — the file says an agent never writes one unasked, and the mark is
    what makes a seed the author's rather than the model's (§3.1).
    """
    marks = json.loads((directory / "reviewed.json").read_text(encoding="utf-8")).get("reviewed", {})
    out: dict[str, dict] = {}
    for case in load_cases(directory):
        if case.provenance != "seeded":
            continue
        mark = marks.get(case.case_id)
        path = directory / f"{case.case_id}.yaml"
        sha = _case_content_sha(path) or None
        if mark is None:
            state = "unreviewed"
        elif not mark.get("sha"):
            state = "unverifiable"
        elif mark["sha"] == sha:
            state = "current"
        else:
            state = "drifted"
        out[case.case_id] = {"state": state, "mark": mark, "sha": sha}
    return out


def review_report(directory: Path = CASES_DIR) -> str:
    status = review_status(directory)
    unreviewed = sorted(k for k, v in status.items() if v["state"] == "unreviewed")
    drifted = sorted(k for k, v in status.items() if v["state"] == "drifted")
    unverifiable = sorted(k for k, v in status.items() if v["state"] == "unverifiable")
    lines = [f"seed review: {len(status) - len(unreviewed)}/{len(status)} marked"]
    if unreviewed:
        lines.append("  UNREVIEWED (no author mark — §3.1 calls these the model's, not the author's):")
        lines += [f"    {c}" for c in unreviewed]
    if drifted:
        lines.append("  DRIFTED (edited since the mark):")
        lines += [f"    {c}" for c in drifted]
    if unverifiable:
        lines.append(
            f"  marked without a content hash, so the mark cannot be checked against the "
            f"current text: {len(unverifiable)} seed(s)"
        )
    return "\n".join(lines)
