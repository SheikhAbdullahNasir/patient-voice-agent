# Patient Voice Agent

A phone-based AI agent that registers new patients through natural conversation. A caller dials
a real phone number, talks to the agent, and their record appears in a REST API and live
dashboard as soon as they confirm. If they call back from the same number, the agent recognises
them and offers to update their existing record instead of creating a duplicate.

A live demo call can be arranged on request (see Contact below).

## Why this project is interesting

- **The backend validates, not the LLM.** An early version asked the model to count phone digits
  itself, and it got it wrong often enough to matter. Now all validation lives in one set of
  Pydantic rules shared by the REST API and the voice tools, and the agent simply reacts to what
  the server says.
- **Errors become conversation.** Tool results are written as instructions to the agent
  (for example, "ask again for only the date of birth"), so a validation error turns into a
  natural re-prompt instead of a dead end.
- **Safe under retries.** Saves are idempotent, so if the agent retries after a timeout, the
  patient is not duplicated.
- **Privacy on duplicates.** When a phone number matches an existing patient, the agent only
  reveals the name before offering an update.

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

`routes/` handles HTTP only and calls `services/` for data logic, which uses `models.py` for the
schema. `schemas.py` holds the validation rules used by both the REST API and the voice tools, so
the two paths can never disagree.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Telephony + voice | Vapi | Real phone number with STT and TTS handled, so effort goes into the prompt and integration |
| LLM | GPT-4.1 (via Vapi) | Reliable tool calling and natural phone conversation |
| Backend | Python + FastAPI | Fast to build, with strong validation through Pydantic |
| Database | PostgreSQL on Supabase | Persistent, real constraints, independent of app hosting |

## Features

- Real phone number and natural LLM conversation
- Full read-back and an explicit "yes" before saving
- Single-field corrections, plus a separate "start over" path
- Re-prompts on invalid data, driven by server-side validation
- REST API with GET/POST/PUT/DELETE, a `{data, error}` envelope, proper status codes
  (200/201/400/404/422/500) and soft delete
- Duplicate detection by phone number
- Read-only dashboard
- 47 automated tests

## How the voice agent works

The LLM has three tools: `lookup_patient(phone)`, `save_patient(...)` and `update_patient(id, ...)`.
Vapi expects HTTP 200 for every tool response, so errors are returned inside the result text and
never as HTTP errors.

### Prompt design (`prompts/system_prompt.md`)
- Voice-first style: short turns, no lists, dates and phone numbers spoken the way people say them
- One or two questions at a time, in a natural order
- Required fields first, then a single opt-in offer for optional fields
- Save is called exactly once, after confirmation
- On any failure: apologise, offer a retry, never go silent

## Edge cases handled

| Situation | Behaviour |
|---|---|
| Invalid date, phone, state or ZIP | Server rejects it and the agent re-asks for only that field |
| Caller corrects a field | Only that field is updated and re-confirmed |
| Caller wants to start over | State resets and collection restarts from the name |
| Call drops mid-call | Nothing is saved, and the end reason is logged |
| Database write fails | The agent apologises and offers a retry |
| Agent retries a save | Idempotent, so no duplicate record |
| Phone matches an existing patient | Agent offers to update instead |
| Caller interrupts mid-sentence | Agent stops and listens |

## Running it locally

```bash
git clone https://github.com/SheikhAbdullahNasir/patient-voice-agent.git && cd patient-voice-agent
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                                   # then fill in the values
python create_tables.py                                # creates the schema
python seed.py                                         # optional demo data
uvicorn app.main:app --reload
```

To expose it publicly for Vapi, run a tunnel such as `ngrok http 8000`, or deploy the container:

```bash
docker build -t patient-agent . && docker run -p 8000:8000 --env-file .env patient-agent
```

Interactive API docs are served at `/docs` and the dashboard at `/dashboard`.

### Environment variables

| Name | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (Supabase Session pooler) |
| `VAPI_SECRET` | Shared secret Vapi sends to `/vapi/*`. Leaving it empty disables the check (local dev only) |

### Vapi setup
1. Create the three Function tools (`lookup_patient`, `save_patient`, `update_patient`) pointing to `/vapi/tools`, plus an End Call tool.
2. Create a Bearer Token credential holding `VAPI_SECRET` and attach it to the tools.
3. Create the assistant using the prompt and first message from `prompts/system_prompt.md`.
4. Set the assistant server URL to `/vapi/events` with the `status-update` and `end-of-call-report` messages.
5. Attach a Vapi phone number to the assistant.

## Tests

```bash
python -m pytest -q
```

47 tests covering validation rules, every REST endpoint, and the voice tools, including the
database-failure path and the shared-secret check. Tests run against the configured database and
clean up the rows they create.

## Observability

Every tool call, the final saved payload, call status, end reason, summary and transcript are
logged to stdout.

## Limitations

- Currently runs locally through an ngrok tunnel. The Dockerfile is tested and ready for an
  always-on host. A live call demo is available on request.
- The REST API has no authentication, since it only holds fictional demo data.
- The free Vapi number accepts US callers only.
- Transcripts are logged, not stored in the database.
- Not HIPAA compliant. Production use would need auth, audit logging and a compliance review.

## Next steps

- Deploy to an always-on host
- Store transcripts linked to the patient record
- Appointment scheduling and Spanish language support
- API authentication, rate limiting, Alembic migrations and CI for the tests

## Contact

Abdullah Bin Nasir · abdullah.nasir7312@gmail.com

## AI assistance

Built with AI coding assistants. I reviewed the code and can explain every design decision.