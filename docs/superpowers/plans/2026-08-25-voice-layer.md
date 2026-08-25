# Voice Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A German-speaking LiveKit voice agent that answers tax-firm status calls from the steuer-graph API and writes call summaries back to the graph.

**Architecture:** `voice/agent.py` runs a LiveKit `AgentSession` with OpenAI Realtime (speech-to-speech). Four `@function_tool`s make thin httpx calls to the existing FastAPI app (`http://127.0.0.1:8000`); all Cypher stays in `app/queries.py`. A new `POST /interaction` endpoint persists caller memory.

**Tech Stack:** Python 3.12/uv, livekit-agents[openai] (~1.6), httpx, FastAPI (existing), neo4j driver (existing), pytest (new dev dep).

## Global Constraints

- No text2cypher at runtime: the LLM only picks tools; user input flows in as parameters only (spec Decision 4).
- All Cypher lives in `app/queries.py` — no queries in `voice/` or `main.py`.
- German, Sie-Form, for all user-facing agent speech and tool docstrings.
- Secrets only in gitignored `.env`; key names documented in `.env.example`; credential values never printed to terminals or chat.
- SteuerClara repo (`C:\Users\cardo\Documents\SteuerClara`) is read-only reference; never modified.
- Commit after every green task (user's standing checkpoint instruction).
- API base URL configurable via `STEUER_GRAPH_API` env var, default `http://127.0.0.1:8000`.

---

### Task 1: `POST /interaction` — caller-memory write-back

**Files:**
- Modify: `app/queries.py` (append at end)
- Modify: `app/main.py` (imports + endpoint at end)
- Test: `tests/test_interaction.py` (new; also creates `tests/`)

**Interfaces:**
- Consumes: existing `run()` helper in `app/main.py:35`, existing Mandant-matching WHERE pattern from `queries.STATUS`.
- Produces: `POST /interaction` accepting JSON `{"mandant": str, "zusammenfassung": str}` → 201 `{"mandant_id": str, "interaction_id": str}` or 404. Task 2's `anruf_protokollieren` tool depends on exactly this contract.

- [ ] **Step 1: Add pytest + httpx as dev dependencies**

```bash
uv add --dev pytest httpx
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_interaction.py`:

```python
"""POST /interaction writes an Interaction node + CALLED edge (against live Aura, self-cleaning)."""

import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from neo4j import GraphDatabase

from app.main import app

load_dotenv()
DB = os.environ.get("NEO4J_DATABASE")


@pytest.fixture()
def driver():
    with GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    ) as d:
        yield d


def test_post_interaction_creates_called_node(driver):
    with TestClient(app) as client:
        resp = client.post(
            "/interaction",
            json={"mandant": "M001", "zusammenfassung": "Testanruf: Status besprochen."},
        )
    assert resp.status_code == 201, resp.text
    iid = resp.json()["interaction_id"]
    try:
        recs = driver.execute_query(
            "MATCH (:Mandant {id:'M001'})-[:CALLED]->(i:Interaction {id:$id}) "
            "RETURN i.zusammenfassung AS z, i.datum IS NOT NULL AS hat_datum",
            id=iid, database_=DB,
        ).records
        assert recs and recs[0]["z"] == "Testanruf: Status besprochen."
        assert recs[0]["hat_datum"] is True
    finally:
        driver.execute_query(
            "MATCH (i:Interaction {id:$id}) DETACH DELETE i", id=iid, database_=DB
        )


def test_post_interaction_unknown_mandant_404():
    with TestClient(app) as client:
        resp = client.post(
            "/interaction", json={"mandant": "gibtesnicht-xyz", "zusammenfassung": "x"}
        )
    assert resp.status_code == 404
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_interaction.py -v`
Expected: FAIL — 404/405 on POST (route does not exist yet).

- [ ] **Step 4: Implement query + endpoint**

Append to `app/queries.py`:

```python
# Write path for the voice layer: one Interaction per call, same Mandant
# matching as STATUS so the agent can pass a spoken name or an id.
LOG_INTERACTION = """
MATCH (m:Mandant)
WHERE m.id = $mandant OR toLower(m.name) CONTAINS toLower($mandant)
CREATE (i:Interaction {id: randomUUID(), datum: datetime(), zusammenfassung: $zusammenfassung})
MERGE (m)-[:CALLED]->(i)
RETURN m.id AS mandant_id, i.id AS interaction_id
"""
```

In `app/main.py`, add to the imports block:

```python
from pydantic import BaseModel
```

and append at the end of the file:

```python
class InteractionIn(BaseModel):
    mandant: str
    zusammenfassung: str


@app.post("/interaction", status_code=201)
async def log_interaction(body: InteractionIn):
    """Persist a call summary as caller memory: Interaction node + CALLED edge."""
    rows = await run(queries.LOG_INTERACTION, mandant=body.mandant, zusammenfassung=body.zusammenfassung)
    if not rows:
        raise HTTPException(404, f"Kein Mandant gefunden für: {body.mandant}")
    return rows[0]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_interaction.py -v`
Expected: 2 passed. (Uses live Aura via `.env`; the created node is deleted by the test.)

- [ ] **Step 6: Commit**

```bash
git add app/queries.py app/main.py tests/test_interaction.py pyproject.toml uv.lock
git commit -m "feat: POST /interaction — caller-memory write-back for the voice layer"
```

---

### Task 2: `voice/agent.py` — LiveKit agent with console-mode verification

**Files:**
- Create: `voice/agent.py`
- Modify: `.env.example` (append voice-layer key names)
- Modify: `pyproject.toml` via `uv add` (livekit-agents, httpx as runtime dep)

**Interfaces:**
- Consumes: `GET /status/{mandant}`, `GET /missing/{mandant}`, `GET /why/{paragraph}`, `POST /interaction` (Task 1 contract) on `STEUER_GRAPH_API`.
- Produces: `uv run python voice/agent.py console|dev` entrypoint; no other module imports `voice/`.

- [ ] **Step 1: Add runtime dependencies**

```bash
uv add "livekit-agents[openai]" httpx
```

- [ ] **Step 2: User action — OPENAI_API_KEY into .env (file-to-file, never echoed)**

```powershell
$line = Get-Content C:\Users\cardo\Documents\SteuerClara\agent\.env | Where-Object { $_ -match '^OPENAI_API_KEY=' } | Select-Object -First 1; Add-Content .env $line
```

Verify presence without printing the value: `Select-String -Path .env -Pattern '^OPENAI_API_KEY=' -Quiet` → `True`.

- [ ] **Step 3: Write `voice/agent.py`**

```python
"""steuer-graph voice agent — LiveKit + OpenAI Realtime.

Terminal dev loop (mic in the terminal, no LiveKit Cloud needed):
  uv run python voice/agent.py console
Register with the LiveKit Cloud project for the browser demo:
  uv run python voice/agent.py dev
"""

import os

import httpx
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, RunContext, function_tool
from livekit.plugins import openai

load_dotenv()

API_BASE = os.environ.get("STEUER_GRAPH_API", "http://127.0.0.1:8000")

# Control token pattern from SteuerClara: a tool result the LLM must act on
# but never read aloud.
FEHLER = (
    "[STEUERUNG – NICHT VORLESEN] Datensatz nicht gefunden oder System nicht "
    "erreichbar. Entschuldige dich kurz und biete einen Rückruf durch eine "
    "Kollegin an."
)

INSTRUCTIONS = """\
Du bist Clara, die freundliche Telefonassistentin einer Steuerkanzlei.
Sprich ausschließlich Deutsch und verwende die Sie-Form.
Antworte in höchstens zwei kurzen Sätzen und stelle höchstens eine Frage pro Antwort.
Sprich Zahlen, Daten und Paragraphen als Wörter (zum Beispiel: "Paragraph neun EStG, Werbungskosten").
Lies niemals JSON, Werkzeugnamen oder rohe Werkzeugausgaben vor — fasse sie natürlich zusammen.
Frage zu Beginn nach dem Namen des Anrufers und verwende diesen Namen für alle Abfragen.
Beantworte Fachfragen nur mit Hilfe deiner Werkzeuge; erfinde keine Informationen.
Liefert ein Werkzeug eine Meldung, die mit [STEUERUNG] beginnt, befolge sie, ohne sie vorzulesen.
Bevor du dich verabschiedest, rufe das Werkzeug anruf_protokollieren mit einer einzeiligen deutschen Zusammenfassung des Gesprächs auf.
"""


async def _get(path: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{API_BASE}{path}")
        if resp.status_code == 404:
            return FEHLER
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError:
        return FEHLER


@function_tool()
async def status_abfragen(context: RunContext, mandant: str) -> str:
    """Liefert den vollständigen Fallstatus eines Mandanten: Fälle, Belege, Fristen, relevante EStG-Paragraphen und die letzten Anrufe. `mandant` ist der Name oder die Mandanten-ID, wie der Anrufer sich vorgestellt hat."""
    return await _get(f"/status/{mandant}")


@function_tool()
async def fehlende_belege(context: RunContext, mandant: str) -> str:
    """Liefert nur die noch fehlenden Belege eines Mandanten samt zugehöriger Fristen. Für die Frage "Was fehlt noch?"."""
    return await _get(f"/missing/{mandant}")


@function_tool()
async def paragraph_erklaeren(context: RunContext, paragraph: str) -> str:
    """Liefert Kontext zu einem EStG-Paragraphen: Thema, Zitierbeziehungen und betroffene Fälle. `paragraph` ist die Nummer, zum Beispiel "9" oder "35a"."""
    return await _get(f"/why/{paragraph}")


@function_tool()
async def anruf_protokollieren(context: RunContext, mandant: str, zusammenfassung: str) -> str:
    """Speichert am Gesprächsende eine einzeilige deutsche Zusammenfassung dieses Anrufs für den Mandanten. Vor der Verabschiedung genau einmal aufrufen."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{API_BASE}/interaction",
                json={"mandant": mandant, "zusammenfassung": zusammenfassung},
            )
        resp.raise_for_status()
        return "[STEUERUNG – NICHT VORLESEN] Zusammenfassung gespeichert. Verabschiede dich freundlich."
    except httpx.HTTPError:
        return "[STEUERUNG – NICHT VORLESEN] Speichern fehlgeschlagen; trotzdem freundlich verabschieden."


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(model="gpt-realtime-2", voice="marin"),
    )
    await session.start(
        room=ctx.room,
        agent=Agent(
            instructions=INSTRUCTIONS,
            tools=[status_abfragen, fehlende_belege, paragraph_erklaeren, anruf_protokollieren],
        ),
    )
    await session.generate_reply(
        instructions="Begrüße den Anrufer auf Deutsch als Assistentin der Kanzlei und frage nach dem Namen."
    )


if __name__ == "__main__":
    # No agent_name: automatic dispatch — the agent joins every new room in
    # the (dedicated, demo-only) LiveKit project. Keeps the hosted Agents
    # Playground working without a dispatch rule.
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
```

- [ ] **Step 4: Document env keys**

Append to `.env.example`:

```
# Voice layer (LiveKit demo project — NOT the SteuerClara prod project)
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
# OpenAI Realtime (copied file-to-file from SteuerClara agent/.env)
OPENAI_API_KEY=
# Optional: where voice tools find the steuer-graph API
# STEUER_GRAPH_API=http://127.0.0.1:8000
```

- [ ] **Step 5: Verify console mode end-to-end (manual)**

Terminal A: `uv run uvicorn app.main:app` — wait for "Application startup complete".
Terminal B: `uv run python voice/agent.py console`, then speak this script (German):
1. Greet → agent asks for name. Say: "Jonas Brückner."
2. "Wie ist der Stand meiner Steuererklärung?" → expect: ESt 2025, wartet auf Belege, § 9/§ 35a spoken with kurznamen.
3. "Was fehlt denn noch?" → expect: Handwerkerrechnung, Nachweis Fahrtkosten, Frist 30. September.
4. "Danke, tschüss." → agent must call anruf_protokollieren before goodbye.

Then verify write-back (expect a NEW Interaction for M002 with today's datum):

```bash
uv run python -c "import os; from dotenv import load_dotenv; from neo4j import GraphDatabase; load_dotenv(); d=GraphDatabase.driver(os.environ['NEO4J_URI'], auth=(os.environ['NEO4J_USERNAME'], os.environ['NEO4J_PASSWORD'])); print(d.execute_query('MATCH (:Mandant {id:\"M002\"})-[:CALLED]->(i) RETURN i.datum, i.zusammenfassung ORDER BY i.datum DESC LIMIT 1', database_=os.environ.get('NEO4J_DATABASE')).records); d.close()"
```

- [ ] **Step 6: Commit**

```bash
git add voice/agent.py .env.example pyproject.toml uv.lock
git commit -m "feat: German voice agent (LiveKit + OpenAI Realtime) over the graph API"
```

---

### Task 3: Browser demo via LiveKit Cloud + README

**Files:**
- Modify: `README.md` (voice section)

**Interfaces:**
- Consumes: Task 2 entrypoint (`voice/agent.py dev`), user-provided `LIVEKIT_URL`/`LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET` in `.env` (new demo project).
- Produces: documented demo procedure; no code contracts.

- [ ] **Step 1: Preflight — LiveKit credentials present (user action if not)**

`Select-String -Path .env -Pattern '^LIVEKIT_URL=.+' -Quiet` → must be `True`.
If `False`: user creates a free project at cloud.livekit.io ("Skip for now" on the Agent Builder screen), copies URL/key/secret from Settings → API Keys into `.env` themselves.

- [ ] **Step 2: Run agent in dev mode**

Terminal A: `uv run uvicorn app.main:app` (if not already running).
Terminal B: `uv run python voice/agent.py dev`
Expected: worker registers with the LiveKit project (log line "registered worker").

- [ ] **Step 3: Verify in Agents Playground (manual)**

Open https://agents-playground.livekit.io, sign in with the LiveKit Cloud account, select the demo project, Connect. Repeat the four-line call script from Task 2 Step 5. Expect identical behavior plus audio in the browser; verify a new Interaction node with the same Cypher one-liner from Task 2 Step 5.

- [ ] **Step 4: README voice section**

Append to `README.md` after the Endpoints section:

```markdown
## Voice layer

German voice agent (LiveKit + OpenAI Realtime) over the endpoints above —
the LLM only ever picks one of four fixed tools; no text2cypher.

​```
uv run uvicorn app.main:app                 # API must be running
uv run python voice/agent.py console        # terminal dev loop (no LiveKit Cloud)
uv run python voice/agent.py dev            # register with LiveKit Cloud project
​```

Browser demo: https://agents-playground.livekit.io → select the demo
project → Connect → speak German. Call summaries are written back as
`(:Mandant)-[:CALLED]->(:Interaction)`.

Env keys: see `.env.example` (LiveKit demo project + `OPENAI_API_KEY`).
```

(Remove the zero-width characters around the inner code fence when pasting — they only keep this plan's Markdown valid.)

- [ ] **Step 5: Run the API tests once more (regression)**

Run: `uv run pytest -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: voice layer demo instructions (console + Agents Playground)"
```
