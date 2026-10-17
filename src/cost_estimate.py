"""What a run cost, including the judge, which the run record leaves out.

`study_case_executions.cost_usd` is the agent plus the simulated member
(runner.py). The judge's tokens are counted per call (`judge.Usage`) but never
persisted, so its share is reconstructed here: every judge prompt is rebuilt
exactly as `judge.py` renders it and its input tokens are counted with Vertex's
`count_tokens` (no generation, nothing written). Output tokens are counted from
the stored rationales wrapped in the response JSON, so they omit any thinking
the judge did; a pair-wise rationale is stored truncated at 1200 characters for
both orderings together, which shortens long pairs further.

Every figure here is a lower bound for the same reason on all three parties:
`candidates_token_count` excludes thinking tokens, which are billed as output.
"""

from __future__ import annotations

import json
from typing import Callable, Optional

from src.cases import Case, load_cases
from src.comparison import _executions
from src.judge import _criteria, _references, _shared_references, _when_block
from src.llm import load_prompt
from src.pricing import PRICING_VERSION, llm_cost_usd
from src.scoring import execution_day, first_reply

JUDGE_MODEL = "gemini-3.5-flash"


def token_counter(model: str = JUDGE_MODEL) -> Callable[[str], int]:
    """Vertex `count_tokens` for one string, with the judge's own client settings."""
    from google import genai
    from google.genai import types

    from src.config import settings

    client = genai.Client(vertexai=True, api_key=settings.VERTEX_API_KEY,
                          http_options=types.HttpOptions(base_url=settings.VERTEX_BASE_URL))
    return lambda text: client.models.count_tokens(model=model, contents=[text]).total_tokens


def _rows(table: str, run_id: str) -> list[dict]:
    from src import db

    return db.admin().table(table).select("*").eq("run_id", run_id).execute().data


def _first_per_execution(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in rows:
        out.setdefault(r["execution_id"], r)
    return out


def pointwise_tokens(case: Case, ex: dict, rationale: str, count: Callable[[str], int]) -> tuple[int, int]:
    """(input, output) tokens of the one point-wise judge call on this execution."""
    request, reply = first_reply(ex)
    if not reply.strip():
        return 0, 0  # never judged: score_execution skips an empty reply
    rendered = load_prompt("judge_pointwise_v1").render(
        user_request=request.strip(), reply=reply.strip(), criteria=_criteria(case),
        references=_references([r.text() for r in case.references], case, execution_day(ex)),
    )
    tokens_in = count(rendered + "\n\nScore the reply.")
    tokens_out = count(json.dumps({"score": 10, "rationale": rationale})) if rationale else 0
    return tokens_in, tokens_out


def pairwise_tokens(case: Case, ex: dict, base: dict, comparison: dict,
                    count: Callable[[str], int]) -> tuple[int, int]:
    """(input, output) tokens of the two pair-wise calls (D23's two orderings)."""
    request, candidate = first_reply(ex)
    _, baseline = first_reply(base)
    prompt = load_prompt("judge_pairwise_v2")
    refs = _shared_references([r.text() for r in case.references], case)
    when_b, when_c = _when_block(case, execution_day(base)), _when_block(case, execution_day(ex))
    tokens_in = 0
    for a, b, wa, wb in ((baseline, candidate, when_b, when_c), (candidate, baseline, when_c, when_b)):
        rendered = prompt.render(
            user_request=request.strip(), reply_a=a.strip() or "(empty reply)",
            reply_b=b.strip() or "(empty reply)", when_a=wa, when_b=wb,
            criteria=_criteria(case), references=refs,
        )
        tokens_in += count(rendered + "\n\nCompare the replies.")
    # Both orderings' rationales are stored as one string, joined by " | " and
    # cut at 1200 characters (comparison.py), so a long pair counts short.
    verdicts = (comparison.get("ordering_candidate_b"), comparison.get("ordering_candidate_a"))
    rationales = (comparison.get("rationale") or "").split(" | ")
    tokens_out = sum(
        count(json.dumps({"better": verdict or "tie", "rationale": rationale}))
        for verdict, rationale in zip(verdicts, rationales) if rationale
    )
    return tokens_in, tokens_out


def places_costs(run_id: str) -> dict[str, dict]:
    """Google Maps Platform calls per execution, from the API's own usage log.

    `api_usage_events` records every billable Google call with the application's
    per-call list estimate (`apps/api/src/lib/pricing.ts`) and the trip it was
    made for. Each repetition builds its own fixture trip, so the trip id
    attributes a call to exactly one execution. Two sources, kept apart:

    - **agent**: calls made during the agent's turns (`/api/ai/agent/chat`) —
      `search_places` and `propose_plan`'s venue lookups.
    - **fixture**: calls made while the harness builds the trip — creating a
      block runs a nearby search to resolve its place. Test setup, not agent
      behaviour, and the same for every execution.
    """
    from src import db

    executions = _executions([run_id])
    by_trip = {(ex.get("fixture_ids") or {}).get("trip"): ex["id"] for ex in executions}
    trips = [t for t in by_trip if t]
    events: list[dict] = []
    for i in range(0, len(trips), 50):
        events += (db.admin().table("api_usage_events")
                   .select("trip_id, provider, api_route, estimated_cost_usd")
                   .in_("trip_id", trips[i:i + 50]).like("provider", "google%").execute().data)
    out: dict[str, dict] = {}
    for e in events:
        source = "agent" if (e.get("api_route") or "").endswith("/ai/agent/chat") else "fixture"
        bucket = out.setdefault(by_trip[e["trip_id"]], {})
        bucket[f"{source}_calls"] = bucket.get(f"{source}_calls", 0) + 1
        bucket[f"{source}_usd"] = bucket.get(f"{source}_usd", 0.0) + float(e.get("estimated_cost_usd") or 0)
    return out


def run_costs(run_id: str, *, baseline_cases: Optional[dict] = None,
              count: Optional[Callable[[str], int]] = None) -> "DataFrame":
    """One row per execution: simulation cost as recorded, judge tokens and cost as estimated.

    `baseline_cases` (the `cases` map of a baseline file) adds the pair-wise
    comparison's two calls; leave it out for a run that was only scored.
    """
    import pandas as pd

    count = count or token_counter()
    cases = {c.case_id: c for c in load_cases()}
    scores = _first_per_execution(_rows("study_scores", run_id))
    comparisons = _first_per_execution(_rows("study_comparisons", run_id)) if baseline_cases else {}
    base_rows = ({e["id"]: e for e in _executions(sorted({v["run_id"] for v in baseline_cases.values()}))}
                 if baseline_cases else {})
    places = places_costs(run_id)
    rows = []
    for ex in _executions([run_id]):
        case = cases[ex["case_id"]]
        google = places.get(ex["id"], {})
        p_in, p_out = pointwise_tokens(case, ex, (scores.get(ex["id"]) or {}).get("rationale") or "", count)
        c_in = c_out = 0
        if baseline_cases and ex["id"] in comparisons:
            base = base_rows[baseline_cases[ex["case_id"]]["execution_id"]]
            c_in, c_out = pairwise_tokens(case, ex, base, comparisons[ex["id"]], count)
        rows.append({
            "case": ex["case_id"], "repetition": ex["repetition"],
            "simulation_usd": ex.get("cost_usd") or 0.0,
            "pointwise_in": p_in, "pointwise_out": p_out,
            "pointwise_usd": llm_cost_usd(JUDGE_MODEL, p_in, p_out),
            "pairwise_in": c_in, "pairwise_out": c_out,
            "pairwise_usd": llm_cost_usd(JUDGE_MODEL, c_in, c_out),
            "agent_places_calls": google.get("agent_calls", 0),
            "agent_places_usd": google.get("agent_usd", 0.0),
            "fixture_places_calls": google.get("fixture_calls", 0),
            "fixture_places_usd": google.get("fixture_usd", 0.0),
        })
    frame = pd.DataFrame(rows)
    frame["judge_usd"] = frame["pointwise_usd"] + frame["pairwise_usd"]
    frame["total_usd"] = frame["simulation_usd"] + frame["judge_usd"]
    frame.attrs["pricing_version"] = PRICING_VERSION
    return frame
