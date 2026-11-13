# Conversational regression testing — Trip Tonic

The instantiation of the evaluation pipeline described in Chapter 3 of the
Master's thesis *Conversational Regression Testing for LLM Agents* (Gian Andri
Hofmann, University of St.Gallen), together with the analysis of the participant
round described in Chapter 4.

Trip Tonic — the application in the rest of this repository — is the agent under
test. The testing system is not a module bolted on top of it: it attaches to the
application's own tool and orchestration boundaries, and the simulator drives the
same interface a user does. That is what allows the results to describe the
deployed system rather than a copy of it.

## Getting started

```bash
python -m venv .venv
.venv/Scripts/activate              # Windows; .venv/bin/activate elsewhere
pip install -r requirements.txt
nbstripout --install --attributes notebooks/study/.gitattributes
cp .env.example .env                # then fill it in

python tools/manuscript.py --outline        # check manuscript access works
python tools/check_notebooks.py             # check no study notebook holds output
```

The `nbstripout` install is not optional and not a nicety. Study notebooks query
participant data; the code looks clean while participant rows sit in the stored
output cells, and git history is permanent.

## Layout

```
  src/              implementation
  cases/            test case definitions
  notebooks/sim/    stages 1 to 3.2 — outputs committed (worked examples)
  notebooks/study/  analysis and pilot — outputs stripped
  tools/            manuscript extractor, notebook check
  docs/             event model, plan, decisions, open questions, logs
  migrations/       copies of the study's SQL migrations (record: supabase/migrations/)
  appendix/         this environment, as submitted with the thesis
```

## The documents, and which is which

| File | Answers |
|---|---|
| `CLAUDE.md` | The rules. Read automatically by any session working in this subtree |
| `docs/event-model.md` | What is logged. Invariant 3 refers to this list |
| `docs/IMPLEMENTATION_PLAN.md` | What is to be built, in what order, at which tier |
| `docs/OPEN_QUESTIONS.md` | What is not yet decided, and what it blocks |
| `docs/DECISIONS.md` | What was decided, when, by whom, why |
| `docs/IMPLEMENTATION_LOG.md` | Where the difficulty actually went (§3.7) |
| `docs/REVIEW_LOG.md` | What was reviewed and accepted (§3.4 transparency) |

`OPEN_QUESTIONS.md` and `DECISIONS.md` are deliberately separate files. A
question the author has not ruled on is not a decision, and recording it as one
misstates the escalation record the thesis reports.

## Reading the manuscript

The manuscript is a `.docx`, which Claude Code cannot open. `tools/manuscript.py`
extracts from it read-only:

```bash
python tools/manuscript.py --outline           # every heading
python tools/manuscript.py --section 3.4       # one numbered section
python tools/manuscript.py --table 11          # one table, as markdown
python tools/manuscript.py --search "pass rate"
python tools/manuscript.py --which             # which revision is being read
```

It finds the newest `MA_Thesis_*.docx` in the thesis folder. Set `MA_MANUSCRIPT`
to pin one exact revision. It never writes to the manuscript or the thesis
folder.

## Sessions

| Command | Tier | Purpose |
|---|---|---|
| `/thesis-plan` | Fable | Once. Produce the plan and the gap list |
| `/thesis-resume` | Fable | Report state, work the next `[FABLE]` task, dispatch `[STANDARD]` ones |
| `/thesis-standard` | cheaper | Work one fully-specified `[STANDARD]` task |
| `/thesis-review` | Fable | Review completed `[STANDARD]` work, record it |

Run them from the **repository root**, not from this folder: the work spans both
the application (Phase A instrumentation) and this subtree, and a session started
here cannot reach `apps/`.

## Status

Environment set up 2026-09-17. `docs/event-model.md` was reviewed and corrected
by the author the same day, and `/thesis-plan` has been run: the plan in
`docs/IMPLEMENTATION_PLAN.md` holds 33 tasks across the three phases, and
`docs/OPEN_QUESTIONS.md` lists the questions that need the author's ruling
before most of Phase A can start. No implementation yet.
