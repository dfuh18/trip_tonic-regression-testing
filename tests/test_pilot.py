"""Offline tests for the pilot checks (C01).

The done-when of C01 is two-sided: the notebook must fail on an empty database
*with the full field list*, and pass on a complete walk through the flow. Both
are tested here against rows built in memory, shaped as PostgREST returns them,
so neither side depends on what happens to be in the shared project today.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src import pilot
from src.pilot import PilotData

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
MODEL = ("gemini-3.5-flash", "2026-05-19")
VERSION = "2026-10-01"


def at(minutes: float) -> str:
    return (T0 + timedelta(minutes=minutes)).isoformat()


def turn(sid: str, n: int, minute: float, **extra) -> dict:
    row = {
        "id": f"{sid}-t{n}", "session_id": sid, "user_id": f"u-{sid}", "trip_id": f"trip-{sid}",
        "run_id": f"run-{sid}", "turn_index": n, "user_turn": "(text)", "user_message_id": f"m-{sid}-{n}",
        "reply_message_id": f"r-{sid}-{n}", "agent_intent": "find", "device_type": "desktop",
        "occurred_at": at(minute), "completed_at": at(minute + 0.2), "latency_ms": 12000, "llm_calls": 2,
        "tool_calls": 1, "tokens_input": 900, "tokens_output": 120, "retry_count": 0,
        "model_version": MODEL[0], "model_released_on": MODEL[1],
        "tool_call_trace": [{"kind": "tool", "seq": 1, "tool": "search_places"}],
        "resulting_state_shape": {"draft": {"suggestion_id": f"d-{sid}-{n}", "slots": 2}},
        "request_type": "venue_lookup", "request_type_rule_version": "rt/1", "error_code": None,
        "user_action": None, "structural_check_outcome": None,
    }
    row.update(extra)
    return row


def complete() -> PilotData:
    """The C04 walk: two consented accounts (one submits, one dismisses), one decline."""
    sessions = [
        {"id": "a", "user_id": "u-a", "run_type": "pilot", "consent_version": VERSION, "consent_at": at(0),
         "declined_at": None, "device_type": "desktop", "client_session_id": "c-a", "created_at": at(0)},
        {"id": "b", "user_id": "u-b", "run_type": "pilot", "consent_version": VERSION, "consent_at": at(1),
         "declined_at": None, "device_type": "tablet", "client_session_id": "c-b", "created_at": at(1)},
        {"id": "c", "user_id": "u-c", "run_type": "pilot", "consent_version": None, "consent_at": None,
         "declined_at": at(2), "device_type": "desktop", "client_session_id": "c-c", "created_at": at(2)},
    ]
    demographics = [
        {"session_id": sid, "user_id": f"u-{sid}", "age": 30, "gender": "prefer_not_to_say",
         "education_level": "master_or_higher", "llm_familiarity": "weekly", "submitted_at": at(minute)}
        for sid, minute in (("a", 3), ("b", 4))
    ]
    suggestions = [turn(sid, n, base + 5 * n) for sid, base in (("a", 5), ("b", 6)) for n in (1, 2, 3)]
    suggestions[0]["user_action"] = "accepted"
    suggestions[3]["user_action"] = "rejected"
    user_actions = [
        {"id": "ua1", "suggestion_id": "a-t1", "target": "slot:2026-11-07:0", "action": "accepted",
         "actor_user_id": "u-a", "created_at": at(12)},
        {"id": "ua2", "suggestion_id": "b-t1", "target": "edits", "action": "rejected",
         "actor_user_id": "u-b", "created_at": at(13)},
    ]
    post_task = [
        {"session_id": "a", "user_id": "u-a", "umux_lite_capability": 6, "umux_lite_ease": 5, "real_trip": False,
         "likelihood_to_recommend": 5, "free_text": "(text)", "submitted_at": at(30), "dismissed_at": None},
        {"session_id": "b", "user_id": "u-b", "umux_lite_capability": None, "umux_lite_ease": None,
         "real_trip": None, "likelihood_to_recommend": None, "free_text": None, "submitted_at": None,
         "dismissed_at": at(31)},
    ]
    feedback = [
        {"id": "f1", "session_id": "a", "user_id": "u-a", "chat_message_id": "r-a-1", "value": "up",
         "created_at": at(14), "updated_at": at(14)},
    ]
    mutations = [
        {"id": "mu1", "table_name": "itinerary_slots", "row_id": "slot1", "op": "INSERT", "changed_keys": ["day_id"],
         "projection": {"day_id": "d"}, "origin_suggestion_id": "a-t1", "origin_kind": "agent_draft_accepted",
         "actor_user_id": "u-a", "session_id": "a", "trip_id": "trip-a", "occurred_at": at(12)},
        {"id": "mu2", "table_name": "trip_blocks", "row_id": "b1", "op": "UPDATE", "changed_keys": ["title"],
         "projection": {"type": "food"}, "origin_suggestion_id": None, "origin_kind": "user_manual",
         "actor_user_id": "u-b", "session_id": "b", "trip_id": "trip-b", "occurred_at": at(20)},
    ]
    return PilotData(sessions, demographics, post_task, suggestions, user_actions, feedback, mutations)


def statuses(checks) -> dict[str, str]:
    return {c.name: c.status for c in checks}


# --- section 1 ---------------------------------------------------------------


def test_empty_database_fails_with_every_required_field():
    checks = pilot.field_population(PilotData())
    failing = {(c.table, c.column) for c in checks if c.status == "FAIL"}
    required = {
        pilot.FIELD_COLUMNS.get(key, key) for key in pilot.event_model_fields()
    } - set(pilot.EXEMPT)
    assert failing == required
    assert pilot.column_population(PilotData())[0].column == "*"


def test_complete_walk_populates_every_field_and_column():
    data = complete()
    for check in pilot.field_population(data) + pilot.column_population(data):
        assert check.status in ("PASS", "EXEMPT"), check


def test_pilot_only_fields_are_required_only_in_strict_mode():
    data = complete()
    data.post_task = [p for p in data.post_task if p["submitted_at"]]
    strict = {(c.table, c.column): c.status for c in pilot.field_population(data, strict=True)}
    lenient = {(c.table, c.column): c.status for c in pilot.field_population(data, strict=False)}
    assert strict[("study_survey_post_task", "dismissed_at")] == "FAIL"
    assert lenient[("study_survey_post_task", "dismissed_at")] == "EXEMPT"


def test_renamed_heading_fails_loudly(tmp_path):
    text = pilot.EVENT_MODEL.read_text(encoding="utf-8").replace("## General level", "## Ambient level")
    path = tmp_path / "event-model.md"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="General level"):
        pilot.event_model_fields(path)


# --- section 2 ---------------------------------------------------------------


def run_checks(data: PilotData, now: datetime, version: str = VERSION, strict: bool = True):
    return [
        *pilot.check_consent(data, version),
        pilot.check_order(data),
        *pilot.check_post_task(data, strict),
        *pilot.check_turns(data, MODEL, now),
        pilot.check_user_action(data),
        *pilot.check_links(data),
        pilot.check_ignored_job(data, now),
        pilot.check_devices(data),
    ]


def test_complete_walk_passes_every_flow_check_after_a_day():
    data = complete()
    for s in data.suggestions:
        s["user_action"] = s["user_action"] or "ignored"
    for check in run_checks(data, T0 + timedelta(days=2)):
        assert check.status == "PASS", check


def test_a_draft_consent_text_fails():
    assert statuses(pilot.check_consent(complete(), "2026-09-18-draft"))["consent text is final"] == "FAIL"


def test_a_decline_with_rows_fails():
    data = complete()
    data.suggestions.append(turn("c", 1, 40))
    assert statuses(pilot.check_consent(data, VERSION))["a decline records nothing else"] == "FAIL"


def test_turn_before_questionnaire_fails():
    data = complete()
    data.demographics[0]["submitted_at"] = at(50)
    assert pilot.check_order(data).status == "FAIL"


def test_post_task_before_third_turn_fails():
    data = complete()
    data.post_task[0]["submitted_at"] = at(12)
    assert statuses(pilot.check_post_task(data, True))["post-task fires after the third turn"] == "FAIL"


def test_owed_post_task_fails_in_pilot_and_warns_in_study():
    data = complete()
    data.post_task = data.post_task[:1]
    assert statuses(pilot.check_post_task(data, True))["post-task reached everyone who qualified"] == "FAIL"
    assert statuses(pilot.check_post_task(data, False))["post-task reached everyone who qualified"] == "WARN"


def test_unpinned_model_fails():
    data = complete()
    data.suggestions[2]["model_version"] = "gemini-flash-latest"
    names = statuses(pilot.check_turns(data, MODEL, T0 + timedelta(hours=1)))
    assert names["model is the pinned dated release"] == "FAIL"


def test_hung_turn_fails():
    data = complete()
    data.suggestions[1]["completed_at"] = None
    names = statuses(pilot.check_turns(data, MODEL, T0 + timedelta(hours=1)))
    assert names["every turn completed"] == "FAIL"


def test_ignored_job_is_pending_then_checked():
    data = complete()
    assert pilot.check_ignored_job(data, T0 + timedelta(hours=1)).status == "PENDING"
    assert pilot.check_ignored_job(data, T0 + timedelta(days=2)).status == "FAIL"
    for s in data.suggestions:
        s["user_action"] = s["user_action"] or "ignored"
    assert pilot.check_ignored_job(data, T0 + timedelta(days=2)).status == "PASS"


@pytest.mark.parametrize(
    ("actions", "slots", "expected"),
    [
        ([], 2, None),
        ([{"target": "slot:x:0", "action": "rejected"}], 2, None),
        ([{"target": "slot:x:0", "action": "rejected"}, {"target": "slot:x:1", "action": "rejected"}], 2, "rejected"),
        ([{"target": "slot:x:0", "action": "rejected"}, {"target": "place:p", "action": "accepted"}], 2, "accepted"),
        ([{"target": "edits", "action": "rejected"}], None, "rejected"),
    ],
)
def test_derive_turn_action_matches_the_app_rule(actions, slots, expected):
    assert pilot.derive_turn_action(actions, slots) == expected


def test_user_action_disagreeing_with_its_rows_fails():
    data = complete()
    data.suggestions[0]["user_action"] = "rejected"
    assert pilot.check_user_action(data).status == "FAIL"


def test_mutation_origin_errors_fail():
    data = complete()
    data.mutations[1]["origin_suggestion_id"] = "a-t1"
    assert statuses(pilot.check_links(data))["mutation origins link correctly (D13)"] == "FAIL"


def test_phone_is_a_warning():
    data = complete()
    data.sessions[1]["device_type"] = "mobile"
    assert pilot.check_devices(data).status == "WARN"


# --- section 3 ---------------------------------------------------------------


def test_descriptives_carry_no_ids_or_text():
    data = complete()
    rendered = repr((
        pilot.session_table(data), pilot.turn_metrics(data),
        pilot.distributions(data), pilot.survey_summary(data),
    ))
    for secret in ("u-a", "a-t1", "(text)", "r-a-1", "trip-a", "c-a"):
        assert secret not in rendered
    assert [r["session"] for r in pilot.session_table(data)] == ["D1", "S1", "S2"]


def test_a_turn_whose_trip_was_deleted_is_not_judged_silent():
    data = complete()
    data.suggestions[1].update(reply_message_id=None, trip_id=None)
    names = statuses(pilot.check_turns(data, MODEL, T0 + timedelta(hours=1)))
    assert names["a completed turn has a reply or an error"] == "PASS"
    data.suggestions[1]["trip_id"] = "trip-a"
    names = statuses(pilot.check_turns(data, MODEL, T0 + timedelta(hours=1)))
    assert names["a completed turn has a reply or an error"] == "FAIL"


def test_failed_turn_without_model_fails_the_pin():
    data = complete()
    data.suggestions[2].update(error_code="llm_error", model_version=None, model_released_on=None)
    names = statuses(pilot.check_turns(data, MODEL, T0 + timedelta(hours=1)))
    assert names["model is the pinned dated release"] == "FAIL"


def test_a_place_added_without_a_turn_is_by_design_but_other_agent_kinds_are_not():
    data = complete()
    place = dict(data.mutations[0], id="mu3", table_name="trip_blocks", origin_kind="agent_place_added",
                 origin_suggestion_id=None)
    data.mutations.append(place)
    assert statuses(pilot.check_links(data))["mutation origins link correctly (D13)"] == "PASS"
    data.mutations[0]["origin_suggestion_id"] = None  # an accepted draft slot must carry its turn
    assert statuses(pilot.check_links(data))["mutation origins link correctly (D13)"] == "FAIL"
