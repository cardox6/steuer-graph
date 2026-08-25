"""steuer-graph voice agent — LiveKit + OpenAI Realtime.

Terminal dev loop (mic in the terminal, no LiveKit Cloud needed):
  uv run python voice/agent.py console
Register with the LiveKit Cloud project for the browser demo:
  uv run python voice/agent.py dev
"""

import json
import os

import httpx
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, RunContext, function_tool, get_job_context
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
Du hast über den Graphen Zugriff auf frühere Anrufe dieses Mandanten: Bei Fragen wie "Was hatten wir zuletzt besprochen?" rufe letzte_anrufe_abfragen auf. Behaupte niemals, du hättest kein Gedächtnis.
Bevor du dich verabschiedest, rufe das Werkzeug anruf_protokollieren mit einer einzeiligen deutschen Zusammenfassung des Gesprächs auf.
Nach anruf_protokollieren: sprich deine Verabschiedung und rufe danach das Werkzeug auflegen auf, um das Gespräch zu beenden.
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
async def letzte_anrufe_abfragen(context: RunContext, mandant: str) -> str:
    """Liefert die Zusammenfassungen der letzten Anrufe dieses Mandanten bei der Kanzlei, neueste zuerst. Nutze dieses Werkzeug bei Fragen zu früheren Gesprächen, zum Beispiel "Was hatten wir beim letzten Anruf besprochen?"."""
    raw = await _get(f"/status/{mandant}")
    if raw.startswith("[STEUERUNG"):
        return raw
    try:
        anrufe = json.loads(raw).get("letzte_anrufe") or []
    except json.JSONDecodeError:
        return FEHLER
    if not anrufe:
        return "[STEUERUNG – NICHT VORLESEN] Für diesen Mandanten sind keine früheren Anrufe verzeichnet."
    return json.dumps(anrufe, ensure_ascii=False)


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


@function_tool()
async def auflegen(context: RunContext) -> str:
    """Beendet das Gespräch. Erst aufrufen, nachdem anruf_protokollieren gelaufen ist und du dich verabschiedet hast."""
    speech = context.session.current_speech
    if speech is not None:
        await speech.wait_for_playout()
    get_job_context().shutdown(reason="Gespräch beendet")
    return "[STEUERUNG – NICHT VORLESEN] Gespräch wird beendet."


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(model="gpt-realtime-2", voice="marin"),
    )
    await session.start(
        room=ctx.room,
        agent=Agent(
            instructions=INSTRUCTIONS,
            tools=[status_abfragen, fehlende_belege, paragraph_erklaeren, letzte_anrufe_abfragen, anruf_protokollieren, auflegen],
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
