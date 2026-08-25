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
