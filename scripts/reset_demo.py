"""Reset demo state: delete agent-created Interactions, keep the seeded story.

Seeded interactions have ids like 'I001'; everything the voice agent writes
gets a randomUUID() id — that difference is the whole filter.

Usage: uv run python scripts/reset_demo.py
"""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase


def main() -> None:
    load_dotenv()
    db = os.environ.get("NEO4J_DATABASE")
    with GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    ) as driver:
        n = driver.execute_query(
            "MATCH (:Mandant)-[:CALLED]->(i:Interaction) "
            "WHERE NOT i.id STARTS WITH 'I' DETACH DELETE i RETURN count(*) AS n",
            database_=db,
        ).records[0]["n"]
        remaining = driver.execute_query(
            "MATCH (:Mandant)-[:CALLED]->(i:Interaction) RETURN count(i) AS n",
            database_=db,
        ).records[0]["n"]
        print(f"Deleted {n} agent-created interactions; {remaining} seeded ones remain.")


if __name__ == "__main__":
    main()
