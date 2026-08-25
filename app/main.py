"""steuer-graph API — fixed endpoints over parameterized Cypher.

Run:  uv run uvicorn app.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from neo4j import AsyncGraphDatabase

from app import queries

load_dotenv()
DATABASE = os.environ.get("NEO4J_DATABASE")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One driver for the process lifetime; the driver pools connections itself.
    app.state.driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )
    await app.state.driver.verify_connectivity()
    yield
    await app.state.driver.close()


app = FastAPI(title="steuer-graph", lifespan=lifespan)


async def run(query: str, **params) -> list[dict]:
    result = await app.state.driver.execute_query(query, database_=DATABASE, **params)
    return [r.data() for r in result.records]


@app.get("/status/{mandant}")
async def status(mandant: str):
    """Everything a status call needs: Fälle, Belege, Fristen, §§, letzte Anrufe."""
    rows = await run(queries.STATUS, mandant=mandant)
    if not rows:
        raise HTTPException(404, f"Kein Mandant gefunden für: {mandant}")
    return rows[0]


@app.get("/missing/{mandant}")
async def missing(mandant: str):
    """Only what's blocking the case: fehlende Belege plus zugehörige Fristen."""
    rows = await run(queries.MISSING, mandant=mandant)
    return {"mandant": mandant, "offene_punkte": rows}


@app.get("/why/{paragraph}")
async def why(paragraph: str):
    """Legal context for a paragraph: citations in/out and the cases it governs."""
    rows = await run(queries.WHY, paragraph=paragraph.lstrip("§ ").strip())
    if not rows:
        raise HTTPException(404, f"Paragraph nicht im Graph: {paragraph}")
    return rows[0]
