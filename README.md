# steuer-graph

Voice agent for tax-firm status calls over a Neo4j knowledge graph (one-day hackathon build).

Two subgraphs, joined at `Fall`:

- **Operational**: `Mandant-[:HAT_FALL]->Fall-[:HAT_BELEG]->Beleg`, `Fall-[:HAT_FRIST]->Frist`, plus `Mandant-[:CALLED]->Interaction` for caller memory
- **Legal**: `Paragraph-[:VERWEIST_AUF]->Paragraph` from the public EStG XML
- **Join**: `Fall-[:GOVERNED_BY]->Paragraph`

Runtime is FastAPI + parameterized Cypher via the neo4j Python driver — **no text2cypher at runtime**. The Aura MCP server (`.vscode/mcp.json`) is build-time only, for seeding/inspecting the graph.

## Setup

```
cp .env.example .env   # fill in from the Aura credentials download
uv sync
```

## Build order

```
uv run python seed/run_seed.py                 # seed operational subgraph
# download https://www.gesetze-im-internet.de/estg/xml.zip, unzip BJNR*.xml to data/estg.xml
uv run python ingest/parse_estg.py             # build legal subgraph
uv run uvicorn app.main:app --reload           # API on :8000
```

## Endpoints

- `GET /status/{mandant}` — Fälle, Belege, Fristen, governing §§, last calls (name or id)
- `GET /missing/{mandant}` — fehlende Belege + deadlines
- `GET /why/{paragraph}` — citation network + affected cases for an EStG §

Voice layer comes later.
