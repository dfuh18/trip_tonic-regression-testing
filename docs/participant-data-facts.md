# Participant data — facts for the consent form

Source material for the participant information sheet and consent form
(§4.2.2, Appendix X). Every statement here is what the code and schema do at
commit time on `feat/thesis-regression-testing`, with the file it rests on, so
the form can be written from facts rather than from memory. Where something is
**not yet decided**, it says so in §9 — those gaps must be closed before the
form is final.

Written 2026-09-24; Vertex moved to the EU endpoint 2026-09-25. If the schema,
the flow or the hosting changes, update this file first.

---

## 1. Who is responsible

| | |
|---|---|
| Controller / researcher | Gian Andri Hofmann, Master's student, University of St.Gallen (HSG) |
| Contact | **not set** — `CONTACT_EMAIL` in `apps/web/src/lib/legal-contact.ts` |
| Purpose | Master's thesis: conversational regression testing of an LLM trip-planning agent |
| Applicable law | Swiss FADP; the GDPR where participants are in the EU/EEA |
| Payment | none — voluntary, unpaid, convenience sample (§4.2.2) |

## 2. What the participant does, in order

1. Opens the study link (`/study/join?cohort=study`) → signs up or logs in.
2. **Consent form** (`/study/consent`). Accept, or decline.
   - Decline: records the decline, removes the study flag from the account,
     signs the person out. Nothing else is recorded.
3. **Demographic questionnaire** (`/study/demographics`), four items.
4. **Task briefing** (`/study/tasks`) — the task, and an *Understood, let's
   start* button.
5. Creates a trip, then asks Tonic in the trip chat at least three times;
   thumbs up/down on replies where they want.
6. After the **third** request to Tonic, a four-item questionnaire appears
   once. It can be submitted or dismissed.
7. Free to continue or stop. There is no explicit "end" step.

Consent cannot be skipped by URL or the Back button: every page of the app
redirects an enrolled account to consent until a consent row exists
(`apps/web/src/routes/_protected.tsx`).

**What counts as a request to Tonic:** only chat messages addressed to
Tonic (`@Tonic …`, a `/command`, or a reply to Tonic). The map-based
destination suggestions in the create-trip wizard and the map search call a
different endpoint. They are **not** logged as study turns and do not count
towards the three.

## 3. What is recorded

Recording starts **at consent** and covers only accounts that joined through a
study link and consented (`study_sessions` row with `consent_at`, no
`declined_at`). Nothing below exists for any other user.

### 3.1 Once, per participant

| Data | Values | Table |
|---|---|---|
| Consent timestamp and **consent text version** | e.g. `2026-09-18-draft` | `study_sessions` |
| Cohort | `pilot` or `study` (pilot sessions are excluded from the analysis) | `study_sessions.run_type` |
| Device type | `desktop` / `tablet` / `mobile`, from the browser's user agent — no fingerprinting | `study_sessions`, and on every turn |
| A random browser-session id | opaque string | `study_sessions.client_session_id` |
| Decline timestamp (if declined) | — | `study_sessions.declined_at` |
| **Age** | 18–120 | `study_survey_demographics` |
| **Gender** | woman / man / non-binary / prefer not to say | ″ |
| **Education** | compulsory / vocational / high school / bachelor / master or higher | ″ |
| **Familiarity with AI chatbots** | never / rarely / monthly / weekly / daily | ″ |
| Post-task: UMUX-LITE capability, ease (1–7) | | `study_survey_post_task` |
| Post-task: planning a real trip? (yes/no) | | ″ |
| Post-task: likelihood to recommend (1–7) | | ″ |
| Post-task: optional free text (≤ 4000 chars) | | ″ |
| Whether the post-task screen was submitted or dismissed, and when | | ″ |

### 3.2 Per request to Tonic (`study_suggestions`)

- **A verbatim copy of what the participant wrote** (`user_turn`), plus links
  to the chat message and to Tonic's reply.
- Timing: sent at, completed at, latency.
- How Tonic answered: model id and release date, number of model and tool
  calls, tokens in/out, retries, error code if it failed, and a **trace of
  the tools it used, with their arguments** (e.g. the search terms and places
  it looked up). Tool *results* are reduced to their size, except whether a
  lookup found anything or returned an error.
- `request_type` — a label derived from which tools were used (e.g. place
  lookup, scheduling, factual question).
- `resulting_state_shape` — the structure of the trip after the turn.
- `user_action` — what the participant did with Tonic's suggestion:
  **accepted** (any suggested slot accepted), **rejected** (all rejected, or
  an edit Tonic made was undone), or **ignored** (set automatically by an
  hourly job once a suggestion is 24 h old with no reaction). A fourth value,
  `user_initiated` (the participant added a place Tonic had named by hand), is
  derived during analysis, never written by the app (D12).

### 3.3 Per reaction

| Data | Table |
|---|---|
| Accept / reject of each suggested place or plan slot, with time | `study_user_actions` |
| Thumbs up / down on a Tonic reply (changeable; one per reply) | `study_feedback` |
| Every change to the trip's plan (stops, itinerary slots, days, drafts, plan-B branches): which table, insert/update/delete, **which fields changed**, whether it came from Tonic or from the participant, and a few structural columns — **never a title or a note** | `study_mutations` |

### 3.4 Recorded by the app anyway (not study-specific)

These exist for every user; the study reads them only to resolve the ids
above.

- Account: email, username, display name, optional avatar/preferences.
- The trip itself and **the full chat**, including Tonic's replies (in the
  trip's own tables).
- Hosting logs (IP address, browser, requests) at Render and Supabase.
- Usage analytics (`ux_events`) — **only if the participant clicks Accept on
  the cookie banner**, which is independent of the study consent.

### 3.5 Not recorded

- No location/GPS, no camera or microphone, no contacts.
- No screen or session recording, no keystrokes.
- No third-party analytics: PostHog, Google Analytics and Sentry are wired in
  the code but **not connected** (their keys are unset), so they send nothing.
- Dietary and accessibility preferences, if a participant sets them, are never
  sent to the AI.

## 4. Where it is stored and processed

| What | Where |
|---|---|
| Database and sign-in (all study tables, trips, chat) | Supabase, AWS **eu-north-1, Stockholm, Sweden** |
| Web app (frontend) and API | Render, **Frankfurt, Germany** — both live services (`trip-tonic-web-5ky6`, `trip-tonic-api-5ky6`, behind `www.` / `api.trip-tonic.com`), region confirmed in the Render dashboard 2026-09-25; no other frontend host. `render.yaml` also says `region: frankfurt`, but its service names are the suspended originals, so the dashboard is the evidence |
| Tonic's replies | Google Vertex AI (Gemini), **EU multi-region endpoint** (`aiplatform.eu.rep.googleapis.com`) — the request (message, trip context, recent chat, travel style) is **processed within the EU**. Default in `apps/api/src/lib/env.ts` (`DEFAULT_VERTEX_BASE_URL`), not an env var, so a deployment cannot drift back to the global endpoint |
| Automated judge and simulator (analysis) | Same EU endpoint (`research/regression-testing/src/config.py`) — participant requests and replies re-read by the judge stay in the EU |
| Place search and details | Google Maps Platform — Google does not guarantee EU-only processing; searches **may be processed in the USA**. The only processing that may leave the EU/CH |

Study data stays in the database. It is never exported into the repository;
analysis runs in notebooks whose outputs are stripped before commit.

## 5. Who can see it

- **The researcher**, through the database's service key and the Supabase
  dashboard — the only full read access.
- **The participant** can read their own consent, questionnaire and request
  rows (row-level security), and download them via *Export my data* on the
  profile page (demographics, post-task answers, request copies).
- **Other members of the participant's trip** see the trip chat, including the
  requests to Tonic and its replies — as for any user. A solo trip has no
  other members.
- **No admin screen** in the app shows any of this content; in-app admin
  analytics are aggregate and pseudonymous only
  (`docs/DECISION_ai_conversation_privacy.md`).

## 6. How it is used in the study

- **Descriptive:** counts of requests, session length, distribution of
  request types, demographics — reported in aggregate only.
- **Failure rates:** how often Tonic failed to produce a valid answer,
  compared between the participant round and simulated test runs (P2).
- **Coverage:** whether the kinds of requests participants make are covered
  by the automated test suite, compared via the tool-use pattern of each
  request (P1).
- **User signals:** accept/reject/ignore and thumbs, set against automated
  quality scores (P3). This involves **sending each participant request and
  Tonic's reply to Gemini a second time**, as an automated judge that scores
  the reply against a rubric. It receives only the request, the reply and the
  rubric — no name, no account id. *(Planned — C02; the judge has so far run
  only on simulated data.)*
- **Usability:** UMUX-LITE and recommend scores.
- Participant conversations are **not** checked against the test suite's
  structural rules (D73).

## 7. Withdrawal and deletion

- Stopping: close the app at any time; no reason needed.
- **Withdrawal = deleting the account** (profile page → Delete account). This
  deletes every study row immediately and permanently (all study tables
  cascade from the account, D14), deletes trips where the participant is the
  only member (and with them the chat), and disassociates the rest.
- Deleting only a *trip* does **not** delete the study rows: the copy of each
  request in `study_suggestions` stays until the account is deleted.
- After the analysis has been reported, deletion still removes the rows, but
  results already computed from them cannot be recalled.

## 8. Cookies and local storage

- Always on: Supabase sign-in cookies; local storage for UI choices and the
  cookie decision.
- Only after *Accept* on the banner: first-party usage events into the same
  database. Reject costs nothing and does not affect the study.

## 9. Decisions in the consent form (`participant-information-and-consent_260925.md`)

The form is the text the app renders at `/study/consent`, version
`2026-09-25` (`CONSENT_VERSION`). It settles what this section used to list as
open:

1. **Contact:** gian.hofmann@student.unisg.ch, for the duration of the study
   (`legal-contact.ts`; also on the privacy page).
2. **Retention:** eight months from consent; then the link to the account and
   the text of the messages are removed **automatically**, leaving anonymous
   records of request kinds and outcomes. **Not implemented yet**: no job does
   this today. It needs a scheduled anonymisation job before the first real
   consent turns eight months old.
3. **Quotation:** no participant text is reproduced; results in aggregate,
   individual interactions only described in general terms.
4. **Judge:** stated: messages are sent to Vertex AI "after the study to
   produce automated quality ratings", on the EU endpoint.
5. **Minimum age:** 18, stated as a participation condition and in the
   consent confirmations.
6. **Deletion without deleting the account:** on request to the researcher.
   Needs a written procedure: delete the session (cascades to every study
   table) *and* clear `user_metadata.study`, or the gate sends the person back
   to consent.

Still open: whether Supabase backups keep deleted rows for some days (the form
does not mention backups).
