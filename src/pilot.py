"""The pilot checks (C01): is the participant flow recording what it should?

Used by ``notebooks/study/05_pilot`` for the pilot (C04) and again after the
first real session (C06). Every function here takes plain rows — lists of
dicts, as PostgREST returns them — so the checks are testable offline and the
notebook stays a thin reader.

Three parts, as the plan orders them:

1. **Field population.** Every field of ``docs/event-model.md`` that a
   participant round can produce must be non-null in at least one row. The
   field list is *parsed from that file*, never retyped here, so a field added
   to the event model is checked without anyone remembering to add it. A
   second pass does the same for every column the tables actually return,
   which catches instrumentation columns the event model does not name.
2. **Flow checks.** Consent carries the current version; a decline records
   nothing else; the questionnaire precedes the first turn; the post-task
   screen fires once, after the third turn; the model is the pinned release;
   labels and links agree with the rows they were derived from; the hourly
   ``ignored`` job has run.
3. **Descriptives.** Counts, distributions and summaries — never a participant's
   words, never an id. Sessions are shown as ``S1, S2, …`` in consent order.

Nothing in this module prints. Output is the notebook's business, and the
notebook only ever renders what these functions return.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from src.config import SUBTREE_ROOT

REPO_ROOT = SUBTREE_ROOT.parent.parent
EVENT_MODEL = SUBTREE_ROOT / "docs" / "event-model.md"
CONSENT_TEXT = REPO_ROOT / "apps" / "web" / "src" / "components" / "study" / "consent-text.tsx"
API_ENV = REPO_ROOT / "apps" / "api" / "src" / "lib" / "env.ts"

Row = dict[str, Any]

#: Event-model sections a participant round produces, and the table each lives
#: in. Run and test-case levels are simulation-only and are not checked here.
LEVEL_TABLES: dict[str, str] = {
    "Session level": "study_sessions",
    "`survey_demographics`": "study_survey_demographics",
    "`survey_post_task`": "study_survey_post_task",
    "Suggestion level": "study_suggestions",
    "State mutation level": "study_mutations",
    "General level": "study_suggestions",
}

#: Where an event-model field is stored under another name (event-model.md,
#: "Field → writer"). Everything not listed is ``table.<field>``.
FIELD_COLUMNS: dict[tuple[str, str], tuple[str, str]] = {
    ("study_sessions", "session_id"): ("study_sessions", "id"),
    ("study_suggestions", "suggestion_id"): ("study_suggestions", "id"),
    ("study_suggestions", "conversation_id"): ("study_suggestions", "run_id"),
    ("study_suggestions", "thumb_feedback"): ("study_feedback", "value"),
    ("study_mutations", "mutation_id"): ("study_mutations", "id"),
}

#: Fields and columns a participant round legitimately leaves null everywhere.
#: Each entry says why; anything not here that is always null is a failure.
EXEMPT: dict[tuple[str, str], str] = {
    ("study_suggestions", "structural_check_outcome"): "never written for participants (D73)",
    ("study_suggestions", "error_code"): "set only when a turn fails; a clean pilot has none",
    ("study_suggestions", "trip_id"): "set null if the trip is deleted — checked as a count, not required",
    ("study_suggestions", "agent_intent"): "set only when a turn starts with a /command",
    ("study_sessions", "anonymised_at"): "set only eight months after consent (D91)",
}

#: Present in ``strict`` mode only (the pilot): C04 asks for one post-task
#: submit and one dismiss, and one decline. After a single real session (C06)
#: these are legitimately one-sided, so there they are reported, not required.
PILOT_ONLY: dict[tuple[str, str], str] = {
    ("study_survey_post_task", "dismissed_at"): "one pilot account dismisses the post-task screen",
    ("study_survey_post_task", "submitted_at"): "one pilot account submits it",
    ("study_survey_post_task", "free_text"): "the submitting pilot account writes a line",
    ("study_sessions", "declined_at"): "one throwaway pilot account declines",
}

AGENT_ORIGINS = {"agent_live_edit", "agent_draft_accepted", "agent_place_added"}

#: The hourly job stamps rows older than 24 h (D17); an hour's slack for the
#: schedule plus five minutes for its own run.
IGNORED_AFTER = timedelta(hours=25, minutes=5)
#: A turn still open after this long did not complete — it crashed or hung.
TURN_TIMEOUT = timedelta(minutes=10)
POST_TASK_AFTER = 3


# --- reading the sources of truth --------------------------------------------


def event_model_fields(path: Path = EVENT_MODEL) -> list[tuple[str, str]]:
    """``(table, field)`` for every participant-level field in the event model.

    Reads each ``| Field |`` table under a heading named in ``LEVEL_TABLES`` and
    takes its first column. Raises if a level is missing, so a renamed heading
    fails loudly instead of silently checking nothing.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    level: Optional[str] = None
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            level = next((k for k in LEVEL_TABLES if k in line), None)
            in_table = False
            continue
        if level is None:
            continue
        if line.startswith("| Field |"):
            in_table = True
            seen.add(level)
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("|"):
            match = re.match(r"\|\s*`([a-z_]+)`", line)
            if match:
                out.append((LEVEL_TABLES[level], match.group(1)))
            continue
        in_table = False
    missing = [k for k in LEVEL_TABLES if k not in seen]
    if missing:
        raise ValueError(f"event-model.md has no field table under: {', '.join(missing)}")
    return list(dict.fromkeys(out))


def _ts_constant(path: Path, name: str) -> str:
    match = re.search(rf'{name}\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"{name} not found in {path.name}")
    return match.group(1)


def current_consent_version() -> str:
    return _ts_constant(CONSENT_TEXT, "CONSENT_VERSION")


def pinned_model() -> tuple[str, str]:
    """The API's pinned model id and its release date (root CLAUDE.md, rule 2)."""
    return _ts_constant(API_ENV, "DEFAULT_VERTEX_MODEL"), _ts_constant(API_ENV, "DEFAULT_VERTEX_MODEL_RELEASED")


# --- the data ----------------------------------------------------------------


@dataclass
class PilotData:
    """Every study row of one ``run_type``. Built by ``load`` or by a test."""

    sessions: list[Row] = field(default_factory=list)
    demographics: list[Row] = field(default_factory=list)
    post_task: list[Row] = field(default_factory=list)
    suggestions: list[Row] = field(default_factory=list)
    user_actions: list[Row] = field(default_factory=list)
    feedback: list[Row] = field(default_factory=list)
    mutations: list[Row] = field(default_factory=list)

    def table(self, name: str) -> list[Row]:
        return {
            "study_sessions": self.sessions,
            "study_survey_demographics": self.demographics,
            "study_survey_post_task": self.post_task,
            "study_suggestions": self.suggestions,
            "study_user_actions": self.user_actions,
            "study_feedback": self.feedback,
            "study_mutations": self.mutations,
        }[name]

    def pseudonyms(self) -> dict[str, str]:
        """Session id → ``S1…`` in consent order; declined sessions follow as ``D1…``."""
        consented = sorted((s for s in self.sessions if s.get("consent_at")), key=lambda s: s["consent_at"])
        declined = sorted((s for s in self.sessions if not s.get("consent_at")), key=lambda s: s["created_at"])
        names = {s["id"]: f"S{i}" for i, s in enumerate(consented, 1)}
        names.update({s["id"]: f"D{i}" for i, s in enumerate(declined, 1)})
        return names


def _fetch(client: Any, table: str, column: str, values: list[str]) -> list[Row]:
    rows: list[Row] = []
    for start in range(0, len(values), 100):
        chunk = values[start : start + 100]
        offset = 0
        while True:
            page = client.table(table).select("*").in_(column, chunk).range(offset, offset + 999).execute().data
            rows.extend(page)
            if len(page) < 1000:
                break
            offset += 1000
    return rows


def load(client: Any, run_type: str) -> PilotData:
    """Every study row belonging to sessions of ``run_type``, via the service key."""
    sessions = client.table("study_sessions").select("*").eq("run_type", run_type).execute().data
    ids = [s["id"] for s in sessions]
    suggestions = _fetch(client, "study_suggestions", "session_id", ids)
    return PilotData(
        sessions=sessions,
        demographics=_fetch(client, "study_survey_demographics", "session_id", ids),
        post_task=_fetch(client, "study_survey_post_task", "session_id", ids),
        suggestions=suggestions,
        user_actions=_fetch(client, "study_user_actions", "suggestion_id", [s["id"] for s in suggestions]),
        feedback=_fetch(client, "study_feedback", "session_id", ids),
        mutations=_fetch(client, "study_mutations", "session_id", ids),
    )


# --- 1. field population -----------------------------------------------------


@dataclass(frozen=True)
class FieldCheck:
    table: str
    column: str
    populated: bool
    note: str = ""  # exemption reason, or why it is required

    @property
    def status(self) -> str:
        if self.populated:
            return "PASS"
        return "EXEMPT" if self.note.startswith("exempt:") else "FAIL"


def _populated(rows: Iterable[Row], column: str) -> bool:
    return any(r.get(column) not in (None, "", [], {}) for r in rows)


def _exemption(key: tuple[str, str], strict: bool) -> str:
    if key in EXEMPT:
        return f"exempt: {EXEMPT[key]}"
    if key in PILOT_ONLY and not strict:
        return f"exempt: pilot-only — {PILOT_ONLY[key]}"
    if key in PILOT_ONLY:
        return f"pilot: {PILOT_ONLY[key]}"
    return ""


def field_population(data: PilotData, strict: bool = True) -> list[FieldCheck]:
    """Section 1a: every event-model field, as the event model names it."""
    checks = []
    for table, name in event_model_fields():
        key = FIELD_COLUMNS.get((table, name), (table, name))
        checks.append(FieldCheck(key[0], key[1], _populated(data.table(key[0]), key[1]), _exemption(key, strict)))
    return list(dict.fromkeys(checks))


def column_population(data: PilotData, strict: bool = True) -> list[FieldCheck]:
    """Section 1b: every column the participant tables actually returned.

    A table with no rows returns no columns; it is reported as one failing
    ``*`` entry rather than passing vacuously.
    """
    checks = []
    for table in (
        "study_sessions", "study_survey_demographics", "study_survey_post_task",
        "study_suggestions", "study_user_actions", "study_feedback", "study_mutations",
    ):
        rows = data.table(table)
        if not rows:
            checks.append(FieldCheck(table, "*", False, "table has no rows for this run_type"))
            continue
        for column in sorted({c for r in rows for c in r}):
            checks.append(FieldCheck(table, column, _populated(rows, column), _exemption((table, column), strict)))
    return checks


# --- 2. flow checks ----------------------------------------------------------


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # PASS | FAIL | PENDING | WARN
    detail: str = ""


def _t(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _by_session(rows: Iterable[Row]) -> dict[str, list[Row]]:
    out: dict[str, list[Row]] = {}
    for r in rows:
        out.setdefault(r.get("session_id"), []).append(r)
    return out


def _fail_or_pass(name: str, bad: list[str], ok: str) -> Check:
    return Check(name, "FAIL", "; ".join(bad)) if bad else Check(name, "PASS", ok)


def check_consent(data: PilotData, current_version: str) -> list[Check]:
    names = data.pseudonyms()
    consented = [s for s in data.sessions if s.get("consent_at")]
    declined = [s for s in data.sessions if s.get("declined_at")]
    out = []
    no_version = [names[s["id"]] for s in consented if not s.get("consent_version")]
    out.append(_fail_or_pass("consent carries a version", [f"{', '.join(no_version)} have none"] if no_version else [],
                             f"{len(consented)} consented session(s)"))
    stale = sorted({s["consent_version"] for s in consented if s.get("consent_version") not in (None, current_version)})
    if current_version.endswith("-draft"):
        out.append(Check("consent text is final", "FAIL", f"CONSENT_VERSION is still {current_version!r}"))
    elif stale:
        out.append(Check("consent text is final", "FAIL", f"sessions consented to {stale}, current is {current_version!r}"))
    else:
        out.append(Check("consent text is final", "PASS", current_version))

    sugg, demo, post = _by_session(data.suggestions), _by_session(data.demographics), _by_session(data.post_task)
    leaky = [
        names[s["id"]] for s in declined
        if s.get("consent_at") or sugg.get(s["id"]) or demo.get(s["id"]) or post.get(s["id"])
    ]
    if not declined:
        out.append(Check("a decline records nothing else", "PENDING", "no declined session yet"))
    else:
        out.append(_fail_or_pass("a decline records nothing else", [f"{', '.join(leaky)} have study rows"] if leaky else [],
                                 f"{len(declined)} declined session(s), no consent, no rows"))
    return out


def check_order(data: PilotData) -> Check:
    """Consent → questionnaire → first turn, per session (§4.2.2)."""
    names, bad = data.pseudonyms(), []
    demo = {d["session_id"]: _t(d.get("submitted_at")) for d in data.demographics}
    first: dict[str, datetime] = {}
    for s in data.suggestions:
        t = _t(s["occurred_at"])
        first[s["session_id"]] = min(first.get(s["session_id"], t), t)
    for s in data.sessions:
        consent = _t(s.get("consent_at"))
        if consent is None:
            continue
        d, f = demo.get(s["id"]), first.get(s["id"])
        if d is not None and d < consent:
            bad.append(f"{names[s['id']]}: questionnaire before consent")
        if f is not None and (d is None or f < d):
            bad.append(f"{names[s['id']]}: a turn before the questionnaire")
    return _fail_or_pass("consent → questionnaire → turns", bad, "in order for every session")


def check_post_task(data: PilotData, strict: bool) -> list[Check]:
    names, out = data.pseudonyms(), []
    sugg = _by_session(data.suggestions)
    by_session = _by_session(data.post_task)
    dup = [names.get(k, "?") for k, v in by_session.items() if len(v) > 1]
    both = [names.get(p["session_id"], "?") for p in data.post_task if p.get("submitted_at") and p.get("dismissed_at")]
    neither = [names.get(p["session_id"], "?") for p in data.post_task if not p.get("submitted_at") and not p.get("dismissed_at")]
    out.append(_fail_or_pass("post-task at most once per session", [f"{', '.join(dup)} twice"] if dup else [], "once or not at all"))
    out.append(_fail_or_pass(
        "post-task is submitted xor dismissed",
        ([f"both on {', '.join(both)}"] if both else []) + ([f"neither on {', '.join(neither)}"] if neither else []),
        "every row is exactly one of the two",
    ))
    early = []
    for p in data.post_task:
        at = _t(p.get("submitted_at") or p.get("dismissed_at"))
        if at is None:
            continue
        before = sum(1 for s in sugg.get(p["session_id"], []) if _t(s["occurred_at"]) <= at)
        if before < POST_TASK_AFTER:
            early.append(f"{names.get(p['session_id'], '?')} after {before} turn(s)")
    out.append(_fail_or_pass("post-task fires after the third turn", [f"fired early: {', '.join(early)}"] if early else [],
                             f"never before turn {POST_TASK_AFTER}"))
    owed = [
        names[s["id"]] for s in data.sessions
        if len(sugg.get(s["id"], [])) >= POST_TASK_AFTER and not by_session.get(s["id"])
    ]
    if owed:
        out.append(Check("post-task reached everyone who qualified", "FAIL" if strict else "WARN",
                         f"{', '.join(owed)} had ≥{POST_TASK_AFTER} turns and no post-task row"))
    else:
        out.append(Check("post-task reached everyone who qualified", "PASS", "no session is owed one"))
    return out


def check_turns(data: PilotData, model: tuple[str, str], now: datetime) -> list[Check]:
    names, out = data.pseudonyms(), []
    open_turns = [s for s in data.suggestions if not s.get("completed_at") and now - _t(s["occurred_at"]) > TURN_TIMEOUT]
    out.append(_fail_or_pass("every turn completed", [f"{len(open_turns)} turn(s) never completed"] if open_turns else [],
                             f"{len(data.suggestions)} turn(s)"))
    # A deleted trip takes its chat rows with it and nulls both message links
    # (ON DELETE SET NULL), so only turns whose trip still exists can be judged.
    silent = [
        s for s in data.suggestions
        if s.get("completed_at") and s.get("trip_id") and not s.get("reply_message_id") and not s.get("error_code")
    ]
    out.append(_fail_or_pass("a completed turn has a reply or an error", [f"{len(silent)} have neither"] if silent else [],
                             "every completed turn does"))
    unlabelled = [s for s in data.suggestions if s.get("completed_at") and (not s.get("request_type") or not s.get("request_type_rule_version"))]
    out.append(_fail_or_pass("request_type and its rule version set", [f"{len(unlabelled)} completed turn(s) lack them"] if unlabelled else [],
                             "on every completed turn"))
    # Failed turns included: since D90 the logger falls back to the configured
    # model when a turn fails before the model answers.
    model_id, released = model
    drift = Counter(
        (s.get("model_version"), s.get("model_released_on")) for s in data.suggestions
        if s.get("completed_at") and (s.get("model_version"), s.get("model_released_on")) != (model_id, released)
    )
    out.append(_fail_or_pass("model is the pinned dated release",
                             [f"{n}× {m} / {d}" for (m, d), n in drift.items()],
                             f"{model_id}, released {released}"))
    unknown = [s for s in data.suggestions if s.get("session_id") not in names]
    out.append(_fail_or_pass("every turn belongs to a known session", [f"{len(unknown)} orphan turn(s)"] if unknown else [], "all do"))
    return out


def derive_turn_action(actions: list[Row], slot_total: Optional[int]) -> Optional[str]:
    """Port of ``deriveTurnAction`` (apps/api/src/routes/study/study.actions.core.ts, D12)."""
    if any(a["action"] == "accepted" for a in actions):
        return "accepted"
    if any(a["target"] == "edits" and a["action"] == "rejected" for a in actions):
        return "rejected"
    if slot_total:
        rejected = {a["target"] for a in actions if a["action"] == "rejected" and a["target"].startswith("slot:")}
        if len(rejected) >= slot_total:
            return "rejected"
    return None


def _slot_total(suggestion: Row) -> Optional[int]:
    slots = ((suggestion.get("resulting_state_shape") or {}).get("draft") or {}).get("slots")
    if isinstance(slots, list):
        return len(slots)
    return slots if isinstance(slots, int) else None


def check_user_action(data: PilotData) -> Check:
    """The stored label is the first one the action rows produced, or ``ignored``.

    The app derives the label once and never overwrites it, so it is replayed
    here over the rows in the order they were written.
    """
    by_suggestion: dict[str, list[Row]] = {}
    for a in sorted(data.user_actions, key=lambda a: a["created_at"]):
        by_suggestion.setdefault(a["suggestion_id"], []).append(a)
    bad = []
    for s in data.suggestions:
        rows, expected, first_at = by_suggestion.get(s["id"], []), None, None
        for i in range(1, len(rows) + 1):
            expected = derive_turn_action(rows[:i], _slot_total(s))
            if expected:
                first_at = _t(rows[i - 1]["created_at"])
                break
        stored = s.get("user_action")
        if expected is None:
            if stored in ("accepted", "rejected"):
                bad.append(f"{stored} with no action rows to support it")
        elif stored != expected:
            late = first_at is not None and first_at - _t(s["occurred_at"]) >= timedelta(hours=24)
            if not (stored == "ignored" and late):
                bad.append(f"stored {stored!r}, rows give {expected!r}")
    return _fail_or_pass("user_action agrees with study_user_actions (D12)", bad,
                         f"{len(data.user_actions)} action row(s) over {len(by_suggestion)} turn(s)")


def check_links(data: PilotData) -> list[Check]:
    out = []
    replies = {s.get("reply_message_id") for s in data.suggestions if s.get("reply_message_id")}
    stray = [f for f in data.feedback if f.get("chat_message_id") not in replies]
    out.append(_fail_or_pass("thumbs point at a logged Tonic reply", [f"{len(stray)} rating(s) do not"] if stray else [],
                             f"{len(data.feedback)} rating(s)"))
    session_of = {s["id"]: s["session_id"] for s in data.suggestions}
    bad = []
    for m in data.mutations:
        kind, origin = m.get("origin_kind"), m.get("origin_suggestion_id")
        if kind in AGENT_ORIGINS and origin is None:
            bad.append(f"{kind} without an origin")
        elif kind in AGENT_ORIGINS and session_of.get(origin) != m.get("session_id"):
            bad.append(f"{kind} linked to another session's turn")
        elif kind not in AGENT_ORIGINS and origin is not None:
            bad.append(f"{kind} carries an origin")
    out.append(_fail_or_pass("mutation origins link correctly (D13)", sorted(set(bad)),
                             f"{len(data.mutations)} mutation(s)"))
    return out


def check_ignored_job(data: PilotData, now: datetime) -> Check:
    """The hourly job has stamped every unreacted turn older than 24 h (D17)."""
    old = [s for s in data.suggestions if now - _t(s["occurred_at"]) > IGNORED_AFTER]
    if not old:
        youngest_due = min((_t(s["occurred_at"]) + IGNORED_AFTER for s in data.suggestions), default=None)
        when = f"; re-run after {youngest_due:%Y-%m-%d %H:%M} UTC" if youngest_due else ""
        return Check("ignored job has run", "PENDING", f"no turn is older than 25 h yet{when}")
    missed = [s for s in old if s.get("user_action") is None]
    stamped = sum(1 for s in data.suggestions if s.get("user_action") == "ignored")
    return _fail_or_pass("ignored job has run", [f"{len(missed)} turn(s) older than 25 h still null"] if missed else [],
                         f"{len(old)} turn(s) old enough, {stamped} stamped ignored")


def check_devices(data: PilotData) -> Check:
    names = data.pseudonyms()
    phones = [names[s["id"]] for s in data.sessions if s.get("device_type") == "mobile"]
    if phones:
        return Check("no phones (§4.2.2 instruction)", "WARN", f"{', '.join(phones)} consented on a phone")
    return Check("no phones (§4.2.2 instruction)", "PASS", "laptop, desktop or tablet throughout")


def flow_checks(data: PilotData, strict: bool, now: Optional[datetime] = None) -> list[Check]:
    now = now or datetime.now(timezone.utc)
    return [
        *check_consent(data, current_consent_version()),
        check_order(data),
        *check_post_task(data, strict),
        *check_turns(data, pinned_model(), now),
        check_user_action(data),
        *check_links(data),
        check_ignored_job(data, now),
        check_devices(data),
    ]


# --- 3. descriptives ---------------------------------------------------------


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    p90 = ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]
    return {"n": len(values), "min": ordered[0], "median": statistics.median(ordered), "p90": p90, "max": ordered[-1]}


def session_table(data: PilotData) -> list[dict[str, Any]]:
    """One row per session, pseudonymous: status, turns, duration, reactions."""
    names = data.pseudonyms()
    sugg, post, fb = _by_session(data.suggestions), _by_session(data.post_task), _by_session(data.feedback)
    demo = {d["session_id"] for d in data.demographics}
    out = []
    for sid, name in sorted(names.items(), key=lambda kv: (kv[1][0], int(kv[1][1:]))):
        s = next(x for x in data.sessions if x["id"] == sid)
        turns = sorted(_t(x["occurred_at"]) for x in sugg.get(sid, []))
        p = (post.get(sid) or [{}])[0]
        out.append({
            "session": name,
            "status": "declined" if s.get("declined_at") else "consented",
            "device": s.get("device_type"),
            "questionnaire": sid in demo,
            "turns": len(turns),
            "minutes first→last turn": round((turns[-1] - turns[0]).total_seconds() / 60, 1) if len(turns) > 1 else None,
            "post-task": "submitted" if p.get("submitted_at") else "dismissed" if p.get("dismissed_at") else None,
            "thumbs up": sum(1 for f in fb.get(sid, []) if f.get("value") == "up"),
            "thumbs down": sum(1 for f in fb.get(sid, []) if f.get("value") == "down"),
        })
    return out


def turn_metrics(data: PilotData) -> dict[str, dict[str, Any]]:
    done = [s for s in data.suggestions if s.get("completed_at")]
    pick = lambda key: [float(s[key]) for s in done if s.get(key) is not None]
    return {
        "latency_ms": _summary(pick("latency_ms")),
        "llm_calls": _summary(pick("llm_calls")),
        "tool_calls": _summary(pick("tool_calls")),
        "tokens_input": _summary(pick("tokens_input")),
        "tokens_output": _summary(pick("tokens_output")),
        "retry_count": _summary(pick("retry_count")),
    }


def distributions(data: PilotData) -> dict[str, Counter]:
    tools: Counter = Counter()
    for s in data.suggestions:
        for step in s.get("tool_call_trace") or []:
            if isinstance(step, dict) and step.get("tool"):
                tools[step["tool"]] += 1
    thumbs_by_type: Counter = Counter()
    type_of = {s.get("reply_message_id"): s.get("request_type") for s in data.suggestions}
    for f in data.feedback:
        thumbs_by_type[(type_of.get(f.get("chat_message_id")) or "unlinked", f.get("value"))] += 1
    return {
        "request_type": Counter(s.get("request_type") or "(none)" for s in data.suggestions),
        "user_action": Counter(s.get("user_action") or "(not yet)" for s in data.suggestions),
        "error_code": Counter(s["error_code"] for s in data.suggestions if s.get("error_code")),
        "command used": Counter(s.get("agent_intent") or "(plain message)" for s in data.suggestions),
        "tool": tools,
        "thumbs by request_type": thumbs_by_type,
        "mutation origin × table": Counter((m.get("origin_kind"), m.get("table_name")) for m in data.mutations),
        "action rows": Counter((a.get("target", "").split(":")[0], a.get("action")) for a in data.user_actions),
    }


def survey_summary(data: PilotData) -> dict[str, Any]:
    """Demographic counts and post-task scores. UMUX-LITE on 0–100 (Lewis et al., 2013)."""
    submitted = [p for p in data.post_task if p.get("submitted_at")]
    umux = [
        ((p["umux_lite_capability"] - 1) + (p["umux_lite_ease"] - 1)) / 12 * 100
        for p in submitted
        if p.get("umux_lite_capability") is not None and p.get("umux_lite_ease") is not None
    ]
    return {
        "age": _summary([float(d["age"]) for d in data.demographics if d.get("age") is not None]),
        "gender": Counter(d.get("gender") for d in data.demographics),
        "education_level": Counter(d.get("education_level") for d in data.demographics),
        "llm_familiarity": Counter(d.get("llm_familiarity") for d in data.demographics),
        "UMUX-LITE (0–100)": _summary(umux),
        "likelihood_to_recommend (1–7)": _summary(
            [float(p["likelihood_to_recommend"]) for p in submitted if p.get("likelihood_to_recommend") is not None]
        ),
        "real_trip": Counter(p.get("real_trip") for p in submitted),
        "free text given": sum(1 for p in data.post_task if p.get("free_text")),
    }
