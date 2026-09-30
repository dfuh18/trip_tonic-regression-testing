"""Tests for ``src.participant_judge`` — the P3 judge on participant replies (D110)."""

from src import participant_judge as pj
from src.llm import LlmReply


def turn(tid, *tools, index=1, run="r1", intent=None, request_type=None, user_turn="find me lunch"):
    trace = [{"kind": "tool", "seq": i, "tool": t, "args": {}} for i, t in enumerate(tools)]
    return {"id": tid, "session_id": "s1", "run_id": run, "turn_index": index, "agent_intent": intent,
            "tool_call_trace": trace, "request_type": request_type, "user_turn": user_turn,
            "reply_message_id": f"m-{tid}"}


class FakeLlm:
    model = "fake"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def generate(self, system, user, *, json_schema=None, temperature=0.0):
        self.prompts.append(system)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return LlmReply(text="", parsed=a, tokens_input=0, tokens_output=0, model="fake", retries=0)


def test_every_request_type_has_criteria():
    version, rubrics = pj.load_rubrics()
    assert version == "participant-rubrics/1"
    assert set(pj.REQUEST_TYPES) <= set(rubrics)
    assert all(len(rubrics[t]) >= 3 for t in pj.REQUEST_TYPES)


def test_the_prompt_carries_the_type_rubric_and_no_trip():
    text = pj.render("find me lunch", "Try Pastéis de Belém.", "venue_lookup")
    _, rubrics = pj.load_rubrics()
    assert rubrics["venue_lookup"][0] in text
    assert rubrics["scheduling"][0] not in text
    assert "You do not see the member's trip" in text
    assert "{{" not in text


def test_the_version_names_prompt_and_rubrics():
    assert pj.judge_version() == "judge-participant/1+participant-rubrics/1"


def test_the_opening_turn_of_each_request_is_scored():
    run = [turn("a", "search_places", intent="find"), turn("b", index=2),
           turn("c", "propose_plan", index=3, intent="plan")]
    assert [t["id"] for t in pj.opening_turns(run)] == ["a", "c"]


def test_the_rubric_follows_the_turns_own_type():
    assert pj.request_type_of(turn("a", "get_weather", request_type="factual_qa")) == "factual_qa"
    assert pj.request_type_of(turn("a", "search_places", "propose_plan")) == "scheduling"
    assert pj.request_type_of(turn("a")) == "advisory"


def test_a_score_is_parsed_and_the_right_rubric_sent():
    llm = FakeLlm({"score": 8, "rationale": "fits"})
    s = pj.score_turn(turn("a", "search_places", request_type="venue_lookup"), "Two places.", llm=llm)
    assert (s.score, s.request_type, s.error) == (8, "venue_lookup", None)
    assert pj.load_rubrics()[1]["venue_lookup"][0] in llm.prompts[0]


def test_no_reply_and_no_text_are_explained_not_scored():
    assert pj.score_turn(turn("a"), "", llm=FakeLlm()).error == "no reply to score"
    assert pj.score_turn(turn("a", user_turn=None), "hi", llm=FakeLlm()).error == "no request text (anonymised)"


def test_a_transient_judge_failure_is_retried(monkeypatch):
    monkeypatch.setattr(pj.time, "sleep", lambda s: None)
    llm = FakeLlm(RuntimeError("429 RESOURCE_EXHAUSTED"), {"score": 6, "rationale": "ok"})
    assert pj.score_turn(turn("a"), "hi", llm=llm).score == 6


def test_an_out_of_range_score_is_not_retried():
    s = pj.score_turn(turn("a"), "hi", llm=FakeLlm({"score": 11, "rationale": ""}))
    assert s.score is None and s.error.startswith("judge:")
