# Voice AI Patient Registration Agent

Call the number, register as a new patient by speaking naturally, and see the record
appear instantly in the REST API and dashboard. Call back with the same phone number
and the agent recognises you.

## ⚠️ Please read before testing

This system is currently hosted on my local machine via a secure tunnel (ngrok), not
a cloud server. **Please email or message me before you plan to call or test the API**,
so I can make sure the server is running when you try it. See "Deployment approach and
trade-offs" below for why, and my availability window at the end of this section.

**Contact:** Abdullah Bin Nasir — abdullah.nasir7312@gmail.com — +92 336 2263668
**Availability window for testing:** [Kindly contact me before you plan to call or test the agent]

## Live demo

| | |
|---|---|
| **Phone number** | +1 (732) 605 4382 |
| **API base URL** | https://antsy-reshape-grumble.ngrok-free.dev |
| **Dashboard** | https://antsy-reshape-grumble.ngrok-free.dev/dashboard |
| **Interactive API docs** | https://antsy-reshape-grumble.ngrok-free.dev/docs |
| **Repository** | https://github.com/SheikhAbdullahNasir/patient-voice-agent.git |

**Notes for testing**
- No login is needed. The REST API is open because this is a demo with fictional data (see Limitations).
- **Duplicate detection demo:** a seeded patient exists (Maria Gonzalez). Give phone number
  555-014-2211 during a call and the agent will offer to update her record instead of creating a new one.
- The phone number is a free Vapi number, which supports US callers only.

## Deployment approach and trade-offs

I tried three hosting options for the API, in this order:

1. **Render (free tier).** Deployment succeeded, but Render required adding a payment card
   to verify the account before the free instance would deploy. I chose not to add one for
   a take-home assessment.
2. **SnapDeploy (free tier, no card required).** The Docker build succeeded after fixing a
   `requirements.txt` encoding issue, but the container repeatedly failed its startup health
   check with a database connection error I could not resolve within a reasonable time,
   despite the same configuration working correctly locally and on Render's build.
3. **ngrok**, tunnelling my local machine, which the assessment PDF explicitly lists as an
   accepted option ("ngrok over cloud deploy" is named as an example of a smart trade-off,
   and ngrok is listed among the suggested hosting options).

Given the constraint, I chose to invest further debugging time in the voice
agent's conversation quality, error handling, and test coverage rather than continuing to
troubleshoot a third hosting provider. **A working, fully tested system on ngrok scores
better than more time spent on an unreliable cloud deployment.**

The `Dockerfile` and `.dockerignore` in this repo are complete and were verified to build
successfully; moving to an always-on host later is mainly a matter of resolving the
database connection issue on that platform and repointing four Vapi server URLs. See
"Next steps" for details.

## Architecture

```
Caller ──► Vapi (phone number, speech-to-text, LLM, text-to-speech)
              │ tool calls (HTTPS + shared secret)      │ call events
              ▼                                         ▼
        FastAPI service ─────────────────────► logs (stdout)
         ├─ /vapi/tools   voice tools: lookup / save / update
         ├─ /vapi/events  call status, summary, transcript
         ├─ /patients     REST API (CRUD, soft delete)
         └─ /dashboard    read-only web page
              │
              ▼
        PostgreSQL (Supabase): constraints enforced in the schema
```

Separation of concerns: `routes/` (HTTP only) calls `services/` (data logic), which uses `models.py`
(schema). `schemas.py` holds one set of validation rules shared by the REST API and the voice tools.

## Tech stack and why

| Layer | Choice | Why |
|---|---|---|
| Telephony + voice | Vapi | Real number, STT and TTS handled, so time goes into prompt and integration |
| LLM | GPT-4.1 (via Vapi) | Reliable tool calling and natural phone conversation |
| Backend | Python + FastAPI | Fast to build; Pydantic gives strong validation |
| Database | PostgreSQL on Supabase | Persistent across restarts; real constraints; not tied to app hosting |
| Hosting | ngrok tunnel to local machine | Render and SnapDeploy both hit blockers (see above); ngrok is explicitly accepted by the assessment |

## Requirements coverage

- Real phone number, natural LLM conversation, read-back confirmation, corrections, re-prompts on invalid data
- All fields from the data model, with types and constraints in `app/models.py`
- REST API: GET/POST/PUT/DELETE, `{data, error}` envelope, 200/201/400/404/422/500, soft delete
- Voice agent writes through the same service layer as the API
- Bonus: duplicate detection by phone number, dashboard, automated tests

## How the voice agent works

Three tools are exposed to the LLM: `lookup_patient(phone)`, `save_patient(...)`, `update_patient(id, ...)`.
Tool results are written as instructions to the assistant (for example "ask again for only these fields"),
so a validation error becomes a natural re-prompt. Vapi requires HTTP 200 for every tool response, so
errors are returned in the result text and never as an HTTP error.

### Prompt design (`prompts/system_prompt.md`)
- Voice-first style: short turns, no lists, dates and phone numbers said the way people say them.
- One or two questions at a time, in a natural order.
- Required fields first, then a single opt-in offer for optional fields.
- Full read-back and an explicit yes before saving. Save is called exactly once.
- Corrections change one field. "Start over" is a separate explicit path.
- Server-side validation is the source of truth. The prompt only teaches the agent how to react,
  and does not ask the model to validate data itself (an early version asked the agent to count
  phone digits, which was unreliable — the model now always defers to the backend's validation).
- Failure path: apologise, offer a retry, never go silent.
- Privacy: on a duplicate match, only the name is revealed.

## Setup

```bash
git clone https://github.com/SheikhAbdullahNasir/patient-voice-agent.git && cd patient-voice-agent
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                                   # then fill in the values
python create_tables.py                                # creates the schema
python seed.py                                         # optional demo data
uvicorn app.main:app --reload
```

To expose it publicly, in a second terminal:
```bash
ngrok http --domain=antsy-reshape-grumble.ngrok-free.dev 8000
```

### Environment variables

| Name | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (Supabase Session pooler) |
| `VAPI_SECRET` | Shared secret Vapi sends to `/vapi/*`. Empty disables the check (local dev only) |

### Vapi configuration
1. Create the three Function tools (`lookup_patient`, `save_patient`, `update_patient`) pointing to `/vapi/tools`, plus an End Call tool.
2. Create a Bearer Token credential holding `VAPI_SECRET` and attach it to the tools.
3. Create the assistant with the prompt from `prompts/system_prompt.md` and the first message from that file.
4. Assistant server URL `/vapi/events`, messages `status-update` and `end-of-call-report`.
5. Attach a free Vapi phone number to the assistant.

### Docker (builds successfully; see "Deployment approach" for hosting status)
```bash
docker build -t patient-agent . && docker run -p 8000:8000 --env-file .env patient-agent
```

## Tests
```bash
python -m pytest -q
```
47 tests, all passing. Covers validation rules, all REST endpoints, and the voice tools (including
the database-failure path and the shared-secret check). Tests run against the configured database
and delete the rows they create.

## Observability
Logged to stdout: every tool call, the final saved payload, call status, end reason, summary and transcript.

## Edge cases handled

| Situation | Behaviour |
|---|---|
| Invalid date, phone, state, ZIP | Server rejects it, the agent re-asks for only that field |
| Caller corrects a field | One field is updated and re-confirmed |
| Caller wants to start over | State is reset and collection restarts from the name |
| Call drops mid-call | Nothing is saved. The end reason is logged |
| Database write fails | Tool returns a fallback message, the agent apologises and offers a retry |
| Agent retries a save | Idempotent: an identical record is not duplicated |
| Phone matches an existing patient | Agent offers to update instead |
| Caller interrupts mid-sentence | Agent stops and listens rather than talking over them |

## Known limitations and trade-offs
- **Hosted via ngrok on a local machine**, not an always-on cloud server. See "Deployment approach" above.
  Please contact me before testing so the server can be running.
- **REST API has no authentication.** Acceptable for a demo with fictional data. Production needs auth and audit logging.
- **Free Vapi number is US-only** and cannot place outbound calls.
- **Tests use the real database** (the schema uses PostgreSQL-specific constraints). Rows are cleaned up after each test.
- Transcripts are logged, not stored in the database.
- Not HIPAA compliant. This is a technical assessment.

## Next steps
- Resolve the SnapDeploy (or another provider's) database connection issue to move off ngrok to an
  always-on host; the Dockerfile is ready and tested.
- Store transcripts linked to the patient record; appointment scheduling; Spanish support;
  authentication for the API; migrations with Alembic; CI running the tests; rate limiting.

## AI assistance
Built with AI coding assistants. I reviewed the code and can explain each design decision.