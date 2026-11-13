# Conversational regression testing — Trip Tonic

The instantiation of the evaluation pipeline described in Chapter 3 of a
Master's thesis on conversational regression testing for LLM agents (Gian Andri
Hofmann, University of St.Gallen, 2026; unpublished), together with the analysis
of the participant round described in Chapter 4.

Trip Tonic, a collaborative trip-planning app with an LLM planning agent
("Tonic"), is the agent under test. The testing system is not a module bolted on
top of it: it attaches to the application's own tool and orchestration
boundaries, and the simulator drives the same interface a user does. That is what
allows the results to describe the deployed system rather than a copy of it.

## What this repository is, and what it is not

This folder lives at `research/regression-testing/` inside the Trip Tonic
repository, and is also published on its own so the thesis artifact can be read
without the application. **The application repository is private.** The
standalone copy was cut out of it with `git filter-repo`: it keeps the full
history of this folder (every commit that touched it, with original dates and
messages) and of the study's SQL migrations, and nothing else.

What is here is everything the thesis describes as the artifact: the case
definitions, the simulator, the structural checker, the judge and its prompts,
the analysis code, the notebooks that produced the reported figures, the study's
database schema, and the record of how it was built (plan, decisions, open
questions, review and implementation logs).

What is **not** here, and why:

| Missing | Why | What that means here |
|---|---|---|
| The application (`apps/api`, `apps/web`) | Private repository | Code under `src/` names files such as `apps/api/src/lib/pricing.ts` in comments: these are the application files a constant was mirrored from, kept so the correspondence is checkable by anyone with access. `src/pilot.py` and `src/runner.py` read two application files (the consent text, the web app's version) and will not find them |
| A running system to test | The harness drives a deployed Trip Tonic API, Supabase database and Vertex model | The pipeline cannot be re-run from this repository alone. The simulation notebooks keep their stored outputs for that reason: they are the worked record of the runs the thesis reports |
| The test suite as a runnable gate | Most modules load credentials on import, and several tests read the application files above | The tests in `tests/` are included as documentation of what was checked and are not expected to pass standalone. In the application repository they ran against the configured environment |
| The schema of record | Migrations are authored and applied in the application's `supabase/migrations/` | `migrations/` holds copies of the study's migrations, with their history; see `migrations/README.md` |
| Participant data | Consent: study data stays in the study database, is never committed, and is anonymised eight months after consent | `notebooks/study/` carries code only, with outputs stripped, in every committed version |
| Figures from the participant round | They are drawn from participant data and appear in the thesis itself; `notebooks/study/figures/` is git-ignored | Only the simulation figures (`notebooks/sim/figures/`) are committed. The study notebooks show how each participant-round figure was produced |
| The thesis manuscript | It is unpublished and has never been in any repository | `tools/manuscript.py`, which sessions used to read it, needs a local copy. Section references such as §3.4 point into it |
| The agent session setup (`.claude/`) | Lives at the application repository root | Reproduced verbatim in `appendix/` (A1–A7) |

Some commit messages and documents refer to paths outside this folder for the
same reason. They are left as written: the history is the record of how the
artifact was built, and rewriting it would make that record less true.

## Layout

```
  cases/            the 31 test case definitions
  src/              implementation: simulator, runner, checker, judge, analysis
  src/prompts/      the simulator and judge prompts, versioned
  notebooks/sim/    stages 1 to 3.2 of the pipeline — outputs committed (worked examples)
  notebooks/study/  participant-round analysis and pilot — outputs stripped
  migrations/       copies of the study's SQL migrations
  examples/         printable records: one simulated execution, the author's own pilot session
  tests/            the test suite (see above: not runnable standalone)
  tools/            run scripts, manuscript extractor, notebook check, withdrawal script
  docs/             event model, plan, decisions, open questions, logs
  appendix/         the development environment, as submitted with the thesis
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
| `docs/participant-data-facts.md` | What the study records about a participant, and where |
| `appendix/README.md` | How the agent-assisted development environment was set up |

`OPEN_QUESTIONS.md` and `DECISIONS.md` are deliberately separate files. A
question the author has not ruled on is not a decision, and recording it as one
misstates the escalation record the thesis reports.

## Setting up (inside the application repository)

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

The artifact was built across many Claude Code sessions, tiered by model
(`appendix/README.md` explains why):

| Command | Tier | Purpose |
|---|---|---|
| `/thesis-plan` | Fable | Once. Produce the plan and the gap list |
| `/thesis-resume` | Fable | Report state, work the next `[FABLE]` task, dispatch `[STANDARD]` ones |
| `/thesis-standard` | cheaper | Work one fully-specified `[STANDARD]` task |
| `/thesis-review` | Fable | Review completed `[STANDARD]` work, record it |

They were run from the application repository root, because the work spans both
the application (Phase A instrumentation) and this subtree.

## Status

Complete for the thesis. The simulation rounds (baseline and regression) and the
participant round (opened 2026-10-02, D114) have been run. The analysis is in
`notebooks/sim/` and `notebooks/study/`, and the decisions behind it are in
`docs/DECISIONS.md`.

## License

Two licenses, split by what a file is:

| Covers | License |
|---|---|
| Code: `src/` (except `src/prompts/`), `tests/`, `tools/`, `migrations/`, `cases/`, `conftest.py`, and the code cells of the notebooks | MIT — [`LICENSE`](LICENSE) |
| Writing and results: `docs/`, `appendix/`, `src/prompts/`, `examples/`, the figures and stored outputs in `notebooks/sim/`, and the Markdown files (README, CLAUDE.md) | CC BY 4.0 — [`LICENSE-CC-BY-4.0.txt`](LICENSE-CC-BY-4.0.txt) |

Both allow reuse, including commercial reuse, provided the author is credited.

## Attribution

The thesis is not published. If you reuse this work, credit it as:

> Gian Andri Hofmann, *Conversational regression testing for LLM agents* (code and
> materials of an unpublished Master's thesis), University of St.Gallen, 2026.
> https://github.com/dfuh18/trip_tonic-regression-testing
