# Demo Runbook

## Pre-flight (5 min before)

1. **Aura awake?** AuraDB Free pauses after days of inactivity — check
   [console.neo4j.io](https://console.neo4j.io): Instance-NESSA must say RUNNING
   (resume takes ~1 min if paused).
2. Start everything: `.\demo.ps1` — API window opens, agent registers
   ("registered worker" in the log).
3. Open [agents-playground.livekit.io](https://agents-playground.livekit.io),
   sign in, select the demo project. Don't connect yet.
4. Second browser tab: Aura console → **Query**, database `67f62912`.
5. Fresh memory slate: `uv run python scripts/reset_demo.py` — deletes all
   agent-written Interactions from rehearsals, keeps the seeded story, so
   Call 2's "last call" is exactly the Call 1 the judges just watched.

## Call 1 — the status call (≈90 seconds)

Connect in the playground. Clara greets and asks for your name.

| You say | What happens |
|---|---|
| "Jonas Brückner" | name → `$mandant` parameter, nothing else |
| "Wie ist der Stand meiner Steuererklärung?" | `status_abfragen` → `GET /status/…` |
| "Was fehlt denn noch?" | `fehlende_belege` → `GET /missing/…` — Handwerkerrechnung, Fahrtkosten, Frist 30.09. |
| "Warum ist Paragraph fünfunddreißig a für mich relevant?" | `paragraph_erklaeren` → `GET /why/35a` — legal subgraph on stage |
| "Danke, tschüss." | `anruf_protokollieren` writes the summary, then `auflegen` ends the call |

**Judge line:** "No text2cypher. The LLM only picks one of six fixed tools;
what I say only ever becomes a query *parameter*. Every Cypher statement is
reviewed code in the repo."

## Call 2 — the memory demo (≈45 seconds)

Reconnect (new room, fresh session — Clara has **zero** session memory).

1. "Jonas Brückner."
2. **"Was hatten wir denn beim letzten Anruf besprochen?"** — Clara calls
   the dedicated `letzte_anrufe_abfragen` tool and reads back the summary
   **she herself wrote 60 seconds ago in Call 1**.
3. Hang up.

**Judge line:** "The agent has no memory — the *graph* is the memory. Call 1
wrote an `Interaction` node; Call 2 read it back. Every demo run makes the
next one richer."

Then flip to the Query tab and show the receipt:

```cypher
MATCH (m:Mandant {id:'M002'})-[:CALLED]->(i:Interaction)
RETURN i.datum, i.zusammenfassung ORDER BY i.datum DESC
```

Top rows: both of today's calls, written by the agent.

## Neo4j tools actually used

- **AuraDB Free** — managed Neo4j instance (`67f62912`), EU-hosted.
- **Cypher** — parameterized queries only; idempotent `MERGE` seed with
  uniqueness constraints; `randomUUID()` / `datetime()` for write-back.
- **neo4j Python driver v6** — sync (`GraphDatabase`) for seed/ingest,
  async (`AsyncGraphDatabase`) inside FastAPI, one pooled driver per process.
- **Neo4j Aura MCP server** (per-instance endpoint) — build-time only:
  schema inspection and verification from the AI pair-programmer
  (`get-schema`, `read-cypher`); never in the runtime path.
- **Aura Studio: Query + Explore** — visualization during the demo.
- Deliberately **not** used: text2cypher at runtime, GDS, vector search —
  fixed queries are the safety story.

## Anticipated question: "Why not neo4j-agent-memory / NAMS?"

Our memory is **domain-native**: Interaction nodes live in the same graph as
Mandanten, Fälle and Paragraphen, so one query joins memory to case data —
the context-graph idea in miniature, hand-built. The hosted service (NAMS)
would put memory in a separate database and break that join; the library's
LLM-extraction pipeline would also break our "parameters only, no LLM
writes" safety story. As an upgrade path (preferences, reasoning traces for
audit), the self-hosted library on this same Aura instance is the natural
next step.

## Showing the graph in the Neo4j UI

Aura console → left nav **Studio → Query** (make sure the database dropdown
says `67f62912`). Run these in order; click the **graph** view toggle for
each:

```cypher
// 1. The whole story in one picture: memory ← client → case → law (14 paths)
MATCH p = (:Interaction)<-[:CALLED]-(:Mandant)-[:HAT_FALL]->(:Fall)-[:GOVERNED_BY]->(:Paragraph)
RETURN p LIMIT 50
```

```cypher
// 2. Operational subgraph: clients, cases, documents
MATCH p = (:Mandant)-[:HAT_FALL]->(:Fall)-[:HAT_BELEG]->(:Beleg)
RETURN p LIMIT 50
```

```cypher
// 3. Citation hubs of the EStG (table view)
MATCH (p:Paragraph)<-[:VERWEIST_AUF]-(citing)
WITH p, count(citing) AS zitiert_von ORDER BY zitiert_von DESC LIMIT 10
RETURN p.id AS par, coalesce(p.kurzname, p.titel) AS thema, zitiert_von
```

```cypher
// 4. § 9 Werbungskosten neighborhood in the citation network (graph view)
MATCH p = (:Paragraph {id:'9'})-[:VERWEIST_AUF]-()
RETURN p
```

UI tips: double-click a node to expand its neighbors; drag to pin; the
label chips above the canvas re-color by label. **Explore** (below Query in
the nav) is the no-code alternative — type `Mandant Fall` in its search bar
and expand from there.
