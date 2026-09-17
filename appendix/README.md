# Appendix — the implementation environment

*Set up 17 September 2026, before any implementation work began.*

This folder documents the agent-assisted development environment in which the
conversational regression testing artifact was built. It is included so that the
conditions under which the implementation was produced are inspectable, in the
same way the prompts given to the agent under test are.

It has two parts. **A1–A7** are the rules and session definitions, reproduced as
they stand. **`templates/B1–B5`** are the blank forms of the five documents that
accumulate content during implementation — the plan, the open questions, the
decisions, the implementation log and the review log. Those five are shown empty
on purpose: by the end of the work the live files hold dozens of entries, which
document the project rather than the environment it started from. The forms show
what was set up; the filled files are evidence of what happened in it.

Everything here except this README is **generated from the live files** by
`tools/build_appendix.py`. A hand-copied appendix drifts from the originals over
the weeks of implementation, and a drifted appendix is worse than none — it
reports an environment that never ran. The blank forms are produced by
truncating each live document at a `TEMPLATE-END` marker, so they cannot drift
from the real ones into a second format either. Regenerate before submission
with:

```bash
python tools/build_appendix.py          # rewrite the copies
python tools/build_appendix.py --check  # verify they are current
```

---

## Why the environment is structured this way

The implementation is carried out across many sessions with a coding agent
(Claude Code). Three problems follow from that, and the environment is the
answer to them.

**Sessions do not remember each other.** Every session starts without the
context of the last one. Rules that live in a chat prompt therefore have to be
re-pasted, and drift from what was actually decided. Rules that live in a file
called `CLAUDE.md` are read automatically at the start of every session, by
whichever model is running. So the durable rules are in the repository, not in
prompts, and state that must cross sessions is in files (the plan, the
decisions, the open questions) rather than in anyone's memory.

**Not every task deserves the strongest model.** Sessions are tiered:
architecture, component fusion, anything touching an invariant, and review of
completed work run on the strongest tier; routine implementation against a
precise specification runs on a cheaper one. The tier rule is what makes this
safe — a task may only be tagged `[STANDARD]` if it is specified tightly enough
that executing it requires no design decisions. A cheaper session that has to
decide something has been mis-assigned, and is instructed to stop rather than
decide. Delegated work is reviewed, and the review is recorded (A7).

**An agent will resolve an ambiguity silently if allowed to.** The rules
therefore separate what the agent decides from what the author decides. A fixed
list of choices — what is logged, what counts as a pass or a failure, any
threshold, which model is used, anything requiring a simulation re-run to undo,
and anything the manuscript leaves unspecified — must be escalated with options
and a recommendation, and waited on. An equally explicit list of things *not* to
ask about (code style, library choice, file naming) keeps that escalation
meaningful rather than constant.

## The two rule files

The rules are split across two files because directory-scoped instructions apply
only inside their subtree, while the root file is read for every task in the
repository, including work on the application that has nothing to do with the
study.

**A1 — the root block.** Only what binds repo-wide: no participant data in
version control, the model pinned to a dated release, logging never dropped
silently, and the additive-changes guardrail. That last rule is the load-bearing
one. The study instruments a working application, and if instrumentation altered
the agent's behaviour, the simulation runs and the participant round would
measure two different systems, with nothing in the collected data revealing it.

**A2 — the subtree rules.** Everything else: the six hard invariants, the phase
structure, the notebook rules, the workflow, the tier policy, and the
escalation lists.

## The session definitions

| | | |
|---|---|---|
| **A3** | `thesis-standard` subagent | Executes one specified task. Pinned to Opus 5. Starts cold by design — which is why a `[STANDARD]` specification must be self-contained |
| **A4** | `/thesis-plan` | The planning session. Produces the implementation plan and the list of what the manuscript leaves unspecified. Writes no code |
| **A5** | `/thesis-resume` | The working session. Reports state, works the next strong-tier task, dispatches specified ones |
| **A6** | `/thesis-standard` | A cheaper session executing one specified task directly |
| **A7** | `/thesis-review` | Reviews delegated work against its specifications and against the invariants, and records what was checked and accepted |

The first session deliberately produces a plan and a list of gaps rather than
code. Arbitrating the unknowns is worth more than a first module written over
them.

## The records kept during implementation

Four files, deliberately separate, because they answer different questions and
feed different sections of the thesis.

| File | Answers | Feeds |
|---|---|---|
| `docs/OPEN_QUESTIONS.md` | What is not yet decided, and what it blocks | — |
| `docs/DECISIONS.md` | What was decided, when, by whom, and why | §3.3, §3.4 |
| `docs/REVIEW_LOG.md` | What was reviewed and accepted, and what was not covered | §3.4 |
| `docs/IMPLEMENTATION_LOG.md` | Where the difficulty and effort actually went | §3.7 |

A question the author has not ruled on is not a decision, and recording it as
one would misstate the escalation record. Hence two files rather than one.

`REVIEW_LOG.md` exists because the decisions file records what was *escalated*
but not what was *checked and found sound*. That distinction is the substance of
the transparency caveat, and it cannot be reconstructed after the fact.

`IMPLEMENTATION_LOG.md` is filtered to avoid becoming a development diary, which
would be worth nothing here: an entry is recorded only if it would change how
someone else built this, or if it bears on a claim in the literature chapter.
Only the strongest tier writes to it, since judging what is noteworthy requires
the context a cheap session does not have. **If the implementation proceeds
without substantial friction the log stays thin, and that is itself a result** —
one that supports the specifiability argument more strongly than a list of
struggles would. It is not padded to have something to report.

Every task in the plan also carries an effort estimate, recorded before the work
rather than after, because the implementation log reports effort *relative to
estimate* and that comparison cannot be recovered retrospectively.

## Two supporting scripts

Not reproduced in full here; both are in `tools/`.

`manuscript.py` gives sessions read-only access to named sections and tables of
the manuscript, which is a `.docx` and cannot otherwise be opened by the agent.
It never writes to the manuscript or its folder.

`check_notebooks.py` fails if any notebook under `notebooks/study/` carries
stored output. Study notebooks query participant data from Supabase, so the
exposure is not a data directory but the output cells stored inside the notebook
file — the code looks clean while participant rows sit in the saved output, and
git history is permanent. `nbstripout` is configured as a git filter for that
directory, but a filter is per-clone; this check is what catches a clone where
nobody installed it.

## Contents

**The rules and the sessions**

| File | Source |
|---|---|
| `A1_root-CLAUDE-addition.md` | the thesis section of the repository root `CLAUDE.md` |
| `A2_subtree-CLAUDE.md` | `research/regression-testing/CLAUDE.md` |
| `A3_agent-thesis-standard.md` | `.claude/agents/thesis-standard.md` |
| `A4_skill-thesis-plan.md` | `.claude/skills/thesis-plan/SKILL.md` |
| `A5_skill-thesis-resume.md` | `.claude/skills/thesis-resume/SKILL.md` |
| `A6_skill-thesis-standard.md` | `.claude/skills/thesis-standard/SKILL.md` |
| `A7_skill-thesis-review.md` | `.claude/skills/thesis-review/SKILL.md` |

**The record-keeping forms, blank** — in `templates/`

| File | Source |
|---|---|
| `B1_IMPLEMENTATION_PLAN.md` | `docs/IMPLEMENTATION_PLAN.md` |
| `B2_OPEN_QUESTIONS.md` | `docs/OPEN_QUESTIONS.md` |
| `B3_DECISIONS.md` | `docs/DECISIONS.md` |
| `B4_IMPLEMENTATION_LOG.md` | `docs/IMPLEMENTATION_LOG.md` |
| `B5_REVIEW_LOG.md` | `docs/REVIEW_LOG.md` |

Each keeps its worked format example, since the example is part of the
instruction — it is what tells a session what an entry is supposed to contain.
The `event-model.md` schema is deliberately not reproduced here: it is study
content rather than environment, and belongs with the manuscript's own appendix.
