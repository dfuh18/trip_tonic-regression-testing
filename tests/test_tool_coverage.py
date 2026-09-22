"""Coverage of the agent under test, checked with the unit tests (D50).

A regression suite that never calls a tool cannot notice that tool breaking.
This is the static half — which tools the cases *name* — and it runs on every
commit, so a suite that stops covering something fails here rather than in a
study. The empirical half (which tools a run actually called, with which
parameters) is `src/coverage.py` and is reported by the runner.
"""
import pytest

from src.cases import ALL_TOOL_NAMES, load_cases
from src.coverage import MUST_BE_DECLARED, READ_TOOLS, declared_coverage, tools_named_by


def test_every_tool_the_agent_has_is_named_by_some_case():
    """The measurement that started this: six of twelve tools were named by no
    case, including schedule_block and unschedule_block — two of the four that
    write the itinerary. The agent could have lost both and every run would
    have reported clean."""
    declared = declared_coverage()
    missing = sorted(t for t in MUST_BE_DECLARED if not declared.get(t))
    assert not missing, (
        f"no case names {missing}. A tool no case names is a tool the suite "
        f"asserts nothing about, so a regression in it is invisible."
    )


def test_the_read_tools_are_deliberately_not_required():
    """The agent calls them only when its preloaded context falls short, which
    varies between runs of one case (D28), so a case cannot require one."""
    for tool in READ_TOOLS:
        assert tool not in MUST_BE_DECLARED
    assert READ_TOOLS < set(ALL_TOOL_NAMES)


def test_both_itinerary_writes_that_were_uncovered_now_have_a_case():
    declared = declared_coverage()
    assert declared.get("schedule_block"), "schedule_block is named by no case"
    assert declared.get("unschedule_block"), "unschedule_block is named by no case"


def test_no_case_names_a_tool_the_agent_does_not_have():
    for case in load_cases():
        unknown = tools_named_by(case) - set(ALL_TOOL_NAMES)
        assert not unknown, f"{case.case_id} names {unknown}"


# --- the cold-open rule ----------------------------------------------------

#: Words that make a request refer to a turn that did not happen. Every
#: repetition starts a fresh conversation, so a follow-up written as a diff
#: against its seed — "actually…", "instead…" — asks the agent about something
#: it has never seen, and a correct agent may reasonably ask what it is being
#: contrasted with.
BACK_REFERENCES = ("actually", "instead of that", "as i said", "like i said", "rather than that")


def test_no_follow_up_refers_to_a_conversation_that_did_not_happen():
    """The relation holds between two cases; it must not be visible inside
    either sentence.

    `instead` alone is allowed: "move the tram ride to Sunday instead" contrasts
    with the itinerary the agent can read, which is a referent that exists.
    """
    for case in load_cases():
        opening = case.opening_turn.lower()
        for marker in BACK_REFERENCES:
            assert marker not in opening, (
                f"{case.case_id}: opening turn contains {marker!r}, which refers to a "
                f"previous turn. Every repetition is a fresh conversation."
            )


def test_a_follow_ups_rubric_does_not_name_a_day_its_request_never_mentions():
    """The bug this catches actually shipped: the follow-up asking for a Belém
    morning on the 9th inherited its seed's rubric, which said "on the 7th", so
    a correct agent would have been marked down on all four repetitions.

    `derive()` inherits scoring_criteria wholesale unless the derivation
    replaces them, so a derivation that overrides checks but forgets the rubric
    keeps a rubric the perturbation invalidated.
    """
    import re

    for case in load_cases():
        if case.provenance != "metamorphic":
            continue
        context = f"{case.opening_turn} {case.goal}".lower()
        for criterion in case.scoring_criteria:
            for ordinal in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)\b", criterion.lower()):
                assert ordinal in context, (
                    f"{case.case_id}: rubric says 'the {ordinal}th' but the request and goal "
                    f"never mention it — an inherited criterion the perturbation invalidated."
                )
