"""The simulator (B06, §3.4): an LLM persona that talks to Tonic as a member.

It drives the same interface a member does and nothing else: it writes the
member's message row the way the browser does, calls ``POST /api/ai/agent/chat``
with that row's id, and reads Tonic's reply back from ``chat_messages``. It
never touches the trip. The opening turn is the case's own words, with the
slash command only when the case names one (D21: at most three turns, stopping
earlier when the persona says the goal is met).

Every simulated turn is logged by the application exactly like a member's
(A02), because the simulated account carries a ``simulation`` session. What
this module adds is the persona's side: its prompt version, its model and its
tokens, so the run's cost and provenance include the simulator.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import httpx

from src import db
from src.auth import SimUser
from src.cases import Case
from src.config import settings
from src.ratelimit import limiter
from src.llm import Llm, load_prompt, simulator_llm

#: D21: the simulator's turn cap.
TURN_CAP = 3

NEXT_TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "done": {"type": "boolean"},
        "next_message": {"type": ["string", "null"]},
        "reason": {"type": "string"},
    },
    "required": ["done", "reason"],
}


@dataclass(frozen=True)
class Turn:
    index: int
    user_message_id: str
    status: int
    reply_message_id: Optional[str]
    suggestion_id: Optional[str]
    run_id: Optional[str]
    edit_count: int
    reply_text: str


@dataclass
class SimulationResult:
    case_id: str
    trip_id: str
    turns: list[Turn] = field(default_factory=list)
    stopped: str = "cap"  # done | cap | agent_error
    stop_reason: str = ""
    simulator_model: str = ""
    simulator_prompt_version: str = ""
    simulator_calls: int = 0
    simulator_tokens_input: int = 0
    simulator_tokens_output: int = 0
    simulator_retries: int = 0

    @property
    def suggestion_ids(self) -> list[str]:
        return [t.suggestion_id for t in self.turns if t.suggestion_id]


#: (content, intent) -> Turn. Injected in tests; the real one talks to the API.
Sender = Callable[[str, Optional[str]], Turn]


class Simulator:
    def __init__(self, llm: Optional[Llm] = None, turn_cap: int = TURN_CAP):
        self.llm = llm or simulator_llm()
        self.turn_cap = turn_cap
        self.prompt = load_prompt("simulator_v1")

    def run(self, case: Case, user: SimUser, token: str, trip_id: str, sender: Optional[Sender] = None) -> SimulationResult:
        send = sender or self._sender(user, token, trip_id)
        result = SimulationResult(
            case_id=case.case_id,
            trip_id=trip_id,
            simulator_model=self.llm.model,
            simulator_prompt_version=self.prompt.version,
        )
        system = self.prompt.render(user_profile=case.user_profile.strip(), goal=case.goal.strip())
        transcript: list[tuple[str, str]] = []
        message, intent = case.opening_turn, case.intent
        for index in range(1, self.turn_cap + 1):
            turn = send(message, intent)
            result.turns.append(turn)
            transcript.append(("member", message))
            if turn.status != 200:
                result.stopped, result.stop_reason = "agent_error", f"agent returned {turn.status} on turn {index}"
                return result
            transcript.append(("tonic", turn.reply_text))
            if index == self.turn_cap:
                result.stop_reason = "turn cap reached"
                return result
            decision = self._next(system, transcript, result)
            if decision["done"] or not decision.get("next_message"):
                result.stopped, result.stop_reason = "done", decision.get("reason", "")
                return result
            message, intent = decision["next_message"].strip(), None
        return result

    def _next(self, system: str, transcript: list[tuple[str, str]], result: SimulationResult) -> dict:
        lines = [f"{'You' if who == 'member' else 'Tonic'}: {text}" for who, text in transcript]
        user = "The conversation so far:\n\n" + "\n\n".join(lines) + "\n\nWhat do you type next, or are you done?"
        reply = self.llm.generate(system, user, json_schema=NEXT_TURN_SCHEMA, temperature=0.7)
        result.simulator_calls += 1
        result.simulator_tokens_input += reply.tokens_input
        result.simulator_tokens_output += reply.tokens_output
        result.simulator_retries += reply.retries
        decision = reply.parsed or {}
        if "done" not in decision:
            raise RuntimeError(f"simulator returned no decision: {reply.text[:120]}")
        return decision

    # ---- the member's path -----------------------------------------------------

    def _sender(self, user: SimUser, token: str, trip_id: str) -> Sender:
        member = db.for_user(token)
        headers = db.api_headers(token)
        counter = {"n": 0}

        def send(content: str, intent: Optional[str]) -> Turn:
            counter["n"] += 1
            row = {"trip_id": trip_id, "user_id": user.id, "content": content, "message_type": "text"}
            if intent:
                row["metadata"] = {"intent": intent}
            message_id = member.table("chat_messages").insert(row).execute().data[0]["id"]
            body = {"trip_id": trip_id, "message": content, "message_id": message_id}
            if intent:
                body["intent"] = intent
            # This request is about to make model calls the harness does not
            # make itself, against the same key's quota (D39). It claims them
            # before sending, at the worst case a turn was observed to cost:
            # under-claiming is what exhausted the window in the B15 probe, and
            # the application's own retry cannot recover from a 429 it caused.
            limiter().acquire(settings.AGENT_CALLS_PER_TURN)
            response = httpx.post(f"{settings.API_BASE_URL}/ai/agent/chat", json=body, headers=headers, timeout=200)
            data = response.json().get("data", {}) if response.status_code == 200 else {}
            suggestion = _wait_for_suggestion(message_id)
            reply_id = data.get("message_id") or (suggestion or {}).get("reply_message_id")
            reply_text = _reply_text(reply_id) if reply_id else ""
            return Turn(
                index=counter["n"],
                user_message_id=message_id,
                status=response.status_code,
                reply_message_id=reply_id,
                suggestion_id=(suggestion or {}).get("id"),
                run_id=data.get("run_id"),
                edit_count=int(data.get("edit_count") or 0),
                reply_text=reply_text,
            )

        return send


def _wait_for_suggestion(user_message_id: str, timeout_s: float = 20.0) -> Optional[dict]:
    """The turn's study row, once the logger has completed it (A02 writes it off the response path)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        rows = (
            db.admin()
            .table("study_suggestions")
            .select("id, reply_message_id, completed_at")
            .eq("user_message_id", user_message_id)
            .execute()
            .data
        )
        if rows and rows[0].get("completed_at"):
            return rows[0]
        time.sleep(0.5)
    return rows[0] if rows else None


def _reply_text(message_id: str) -> str:
    rows = db.admin().table("chat_messages").select("content").eq("id", message_id).execute().data
    return rows[0]["content"] if rows else ""
