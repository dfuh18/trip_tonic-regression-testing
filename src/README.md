# Harness environment

The simulator drives the deployed application the way a member does (§3.3):
it signs in, writes the chat row the browser would write, and calls
`POST /api/ai/agent/chat`. Everything it reads back comes from the study
tables Phase A writes. There is one Supabase project for the simulation and
the participant round alike (D15); simulated rows are told apart by
`study_sessions.run_type = 'simulation'`.

## Set-up

```
cp .env.example .env         # fill in the Supabase keys, the Vertex key, a SIM_USER_PASSWORD
python -m src.auth --check   # creates sim-01…, gives each a simulation session, signs each in
```

`API_BASE_URL` points the simulator at an API. For a run of record it is the
deployed API; while developing, the dev server on port 3001. Either way the
API must run with `DEFAULT_SUBSCRIPTION_TIER=pro` for the duration of a run
(D15): the monthly AI cap on the free tier refuses a simulated member after a
handful of cases, and a refused turn is a hole in the data, not a finding.

## Modules

| Module | Role |
|---|---|
| `config.py` | every setting, from the environment; never printed (B14) |
| `db.py` | the admin client (study tables, run rows) and a per-member RLS client |
| `auth.py` | the simulated accounts and their sessions (B01) |
| `cases.py` | the case model and loader; `suite_version` (B03) |
| `signature.py` | the P1 coverage signature (B12) |
| `fixture.py`, `reset.py` | the fixture trip, the state reset and the precondition gate (B02) |
| `simulator.py`, `runner.py`, `checker.py`, `judge.py` | stages 1 to 3.2 (B06–B09) |

## Accounts

Simulated members live at `sim-NN@sim.triptonic.invalid`, an undeliverable
domain, with one password from the environment. They are ordinary members in
every respect the application can see: the same RLS, the same quota, the same
trip tables. They differ only in the session row that marks their turns as
simulation, and they never appear in the participant analysis because that
filters on `run_type`.
