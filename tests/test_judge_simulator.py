"""The judge and the simulator with a scripted model and a scripted API: the
prompt contents, the two-ordering rule of D23, and the turn loop of D21."""
import json
from dataclasses import dataclass, field

import re

import pytest

from src.cases import Case
from src.judge import compare_pairwise, score_pointwise
from src.llm import LlmReply, load_prompt
from src.simulator import Simulator, Turn


@dataclass
class FakeLlm:
    answers: list
    model: str = "fake-model"
    calls: list = field(default_factory=list)

    def generate(self, system, user, *, json_schema=None, temperature=0.0):
        self.calls.append((system, user, temperature))
        answer = self.answers.pop(0)
        return LlmReply(text=json.dumps(answer), parsed=answer, tokens_input=10, tokens_output=5, model=self.model, retries=0)


CASE = Case(
    case_id="venue_lookup_seafood",
    provenance="seeded",
    run_priority=1,
    function="venue_lookup",
    user_profile="Marta, 34.",
    goal="Two seafood places.",
    opening_turn="/find seafood near Cais do Sodré",
    intent="find",
    scoring_criteria=["Names real places.", "Stays in the area."],
    repetitions_n=8,
)


def test_prompts_carry_a_version_header():
    """That a version is declared and stripped from what the model sees — not
    which version it is. Pinning the number makes every legitimate bump fail a
    test, which is how a version stops being bumped."""
    for name in ("simulator_v1", "judge_pointwise_v1", "judge_pairwise_v1"):
        prompt = load_prompt(name)
        assert re.fullmatch(r"[a-z-]+/\d+", prompt.version), prompt.version
        assert "<!--" not in prompt.template


def test_pointwise_inlines_criteria_and_references_and_validates_the_score():
    llm = FakeLlm([{"score": 7, "rationale": "fine"}])
    result = score_pointwise(CASE, "find seafood", "Try Cervejaria Ramiro.", ["Ramiro is a seafood house."], llm=llm)
    # The version is recorded and matches the prompt actually loaded; which
    # number it is belongs in the prompt file, not in an assertion here.
    assert result.score == 7
    assert result.usage.prompt_version == load_prompt("judge_pointwise_v1").version
    system, _, temperature = llm.calls[0]
    assert "- Names real places." in system and "Ramiro is a seafood house." in system and temperature == 0.0
    with pytest.raises(RuntimeError):
        score_pointwise(CASE, "q", "r", llm=FakeLlm([{"score": 11, "rationale": ""}]))


def test_every_judge_call_carries_the_trip_the_request_was_about():
    """Criteria like "fits this trip" are unscorable from the request and the
    reply alone. The summary is prepended here so no caller can forget it —
    including the calls that pass no references at all."""
    from src.fixture import load_fixture, summary

    expected = summary(load_fixture())
    llm = FakeLlm([{"score": 5, "rationale": ""}])
    score_pointwise(CASE, "what should we pack", "Layers.", llm=llm)
    system, _, _ = llm.calls[0]
    assert expected in system

    pair = FakeLlm([{"better": "tie", "rationale": ""}, {"better": "tie", "rationale": ""}])
    compare_pairwise(CASE, "what should we pack", "a", "b", llm=pair)
    assert expected in pair.calls[0][0]


@pytest.mark.parametrize(
    "first, swapped, expected",
    [
        ("B", "A", True),      # candidate wins in both orderings
        ("tie", "tie", True),  # a tie is at least as good
        ("B", "tie", True),
        ("B", "B", False),     # the model preferred position B both times: position bias, not quality
        ("A", "A", False),
        ("A", "tie", False),   # baseline better in one ordering
    ],
)
def test_pairwise_requires_both_orderings(first, swapped, expected):
    llm = FakeLlm([{"better": first, "rationale": ""}, {"better": swapped, "rationale": ""}])
    result = compare_pairwise(CASE, "find seafood", "baseline", "candidate", llm=llm)
    assert result.at_least_as_good is expected
    assert result.usage.calls == 2
    a_first, _, _ = llm.calls[0]
    assert a_first.index("baseline") < a_first.index("candidate")
    a_second, _, _ = llm.calls[1]
    assert a_second.index("candidate") < a_second.index("baseline")


def make_sender(replies):
    sent = []

    def send(content, intent):
        sent.append((content, intent))
        status, text = replies.pop(0)
        n = len(sent)
        return Turn(index=n, user_message_id=f"m{n}", status=status, reply_message_id=f"r{n}" if status == 200 else None,
                    suggestion_id=f"s{n}" if status == 200 else None, run_id="run", edit_count=0, reply_text=text)

    return send, sent


def test_simulator_opens_verbatim_with_intent_and_stops_when_done():
    llm = FakeLlm([{"done": False, "next_message": "and something cheaper?", "reason": "one more"},
                   {"done": True, "next_message": None, "reason": "enough"}])
    send, sent = make_sender([(200, "Here are two."), (200, "Cheaper ones."), (200, "unused")])
    result = Simulator(llm=llm).run(CASE, user=None, token="", trip_id="t", sender=send)
    assert sent[0] == ("/find seafood near Cais do Sodré", "find")
    assert sent[1] == ("and something cheaper?", None)
    assert result.stopped == "done" and len(result.turns) == 2
    assert result.simulator_calls == 2 and result.simulator_prompt_version == "simulator/1"
    assert result.suggestion_ids == ["s1", "s2"]


def test_simulator_stops_at_the_cap_without_asking_again():
    llm = FakeLlm([{"done": False, "next_message": "more", "reason": ""}] * 2)
    send, sent = make_sender([(200, "a"), (200, "b"), (200, "c")])
    result = Simulator(llm=llm).run(CASE, user=None, token="", trip_id="t", sender=send)
    assert result.stopped == "cap" and len(result.turns) == 3 and result.simulator_calls == 2


def test_simulator_stops_on_an_agent_error():
    llm = FakeLlm([])
    send, sent = make_sender([(504, "")])
    result = Simulator(llm=llm).run(CASE, user=None, token="", trip_id="t", sender=send)
    assert result.stopped == "agent_error" and len(result.turns) == 1 and result.simulator_calls == 0
