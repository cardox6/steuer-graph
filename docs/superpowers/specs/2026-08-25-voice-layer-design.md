# Voice Layer Design — steuer-graph

Date: 2026-08-25
Status: approved (pending final spec review)

## Goal

A German-speaking voice agent for tax-firm status calls over the existing
steuer-graph API. Caller states their name, asks about their case, and the
agent answers from the graph — Fälle, fehlende Belege, Fristen, governing
EStG §§, and prior-call memory. No text2cypher at runtime: the LLM only ever
picks one of four fixed tools; user input flows in as parameters.

## Decisions (with rationale)

1. **Channel: LiveKit web voice.** Demo runs in the browser via LiveKit;
   no telephony, no phone number. Dev loop uses LiveKit *console mode*
   (terminal mic, no cloud needed).
2. **Speech stack: OpenAI Realtime speech-to-speech.** One provider, one
   key, server-side voice detection, no local model downloads — the
   "simple and working" choice for a demo. SteuerClara's production
   `pipeline_de` recipe (Deepgram de + LLM + ElevenLabs) was considered and
   deliberately deferred: its German tuning pays off at production call
   volume, not in a demo, and costs two extra vendors plus local
   VAD/turn-detector model setup. It remains the documented upgrade path.
   We still reuse SteuerClara's German prompt rules and tool patterns.
3. **Credentials: hybrid.** Reuse the stateless OPENAI_API_KEY from
   `SteuerClara\agent\.env`; create a **new free LiveKit Cloud project** for
   the demo so prod SIP/dispatch infrastructure stays fully isolated.
   All values live only in the gitignored `.env`.
4. **Data access: tools → httpx → existing FastAPI** (not direct Neo4j).
   All Cypher stays in `app/queries.py`. The demo exercises the real API.
5. **Call memory write-back: yes.** At call end the agent posts a one-line
   German summary; a new `POST /interaction` endpoint MERGEs an
   `Interaction` node + `CALLED` edge, same shape as seeded ones.

## Architecture

```
Browser (LiveKit Agents Playground)      dev: terminal console mode
        │  WebRTC
        ▼
LiveKit Cloud (new demo project)
        │
voice/agent.py  — AgentSession(OpenAI Realtime) + 4 @function_tool
        │  httpx (localhost:8000)
        ▼
app/main.py (FastAPI) ── app/queries.py (all Cypher) ── Aura 67f62912
```

## Components

### voice/agent.py (new)
- `AgentSession` with `openai.realtime.RealtimeModel` (speech-to-speech,
  server-side turn detection/VAD, a German-capable voice picked at
  implementation). No STT/TTS plugins, no local models.
- Four tools, German docstrings (LLM-facing), thin httpx calls:
  - `status_abfragen(mandant)` → `GET /status/{mandant}`
  - `fehlende_belege(mandant)` → `GET /missing/{mandant}`
  - `paragraph_erklaeren(paragraph)` → `GET /why/{paragraph}`
  - `anruf_protokollieren(mandant, zusammenfassung)` → `POST /interaction`
    (called once before hang-up)
- System prompt: German, Sie-Form, adapted from SteuerClara
  `AGENT_INSTRUCTIONS.txt` conversational rules: max 2 sentences per reply,
  one question per reply, numbers/dates as words, never read tool output or
  tool names aloud, ask for the caller's name first, use kurzname-labeled
  paragraph strings as-is.
- Registered under agent name `steuer-graph-demo`.

### app additions
- `queries.py`: `LOG_INTERACTION` — MERGE `(:Interaction {id: randomUUID()})`
  with `datum: datetime()`, `zusammenfassung`, plus `(m)-[:CALLED]->(i)`;
  404 if Mandant unknown.
- `main.py`: `POST /interaction` with pydantic body
  `{mandant: str, zusammenfassung: str}`.

### Environment
`.env` additions (documented in `.env.example`, values never committed):
`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (new demo project —
user creates it in the LiveKit console and fills these in),
`OPENAI_API_KEY` (copied locally from `SteuerClara\agent\.env`,
file-to-file, never through chat or terminals that echo values).

Dependencies added via uv: `livekit-agents[openai]`, `httpx`.

## Error handling
- API unreachable / Mandant not found / any tool exception → tool returns a
  German control string ("Datensatz nicht gefunden…"); the prompt instructs
  the agent to apologize and offer a callback by a colleague. Tools never
  raise into the voice loop.
- `POST /interaction` failure at call end is logged, not spoken.

## Testing
1. Unit-ish: run FastAPI, call the four HTTP paths directly (curl) including
   the new POST, verify Interaction node lands in Aura (via MCP).
2. Console mode: `uv run python voice/agent.py console` — scripted German
   call: name → status → missing → why → hang up; verify write-back node.
3. Browser: connect Agents Playground to the new LiveKit project, repeat.

## Checkpoints (commit after each)
1. `POST /interaction` endpoint + query, smoke-tested.
2. Working console-mode agent.
3. Playground/browser demo verified + README voice section.

## Out of scope (YAGNI)
Telephony/SIP, multi-tenant anything, Langfuse/observability, custom web
frontend, thinking/ambient sounds, parallel transcription, strategy/role
system, autoscaling. SteuerClara remains untouched (read-only reference).

Deferred upgrade path: swap the Realtime model for SteuerClara's
`pipeline_de` profile (Deepgram nova-3 de + LLM + ElevenLabs with tuned
voice settings) if German STT/TTS quality needs production polish.
