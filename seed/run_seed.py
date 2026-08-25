"""Execute seed/seed.cypher against Aura, one statement at a time.

Usage: uv run python seed/run_seed.py
"""

import os
import pathlib

from dotenv import load_dotenv
from neo4j import GraphDatabase

CYPHER_FILE = pathlib.Path(__file__).with_name("seed.cypher")


def main() -> None:
    load_dotenv()
    statements = [s.strip() for s in CYPHER_FILE.read_text(encoding="utf-8").split(";") if s.strip()]
    with GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    ) as driver:
        db = os.environ.get("NEO4J_DATABASE")
        for stmt in statements:
            driver.execute_query(stmt, database_=db)
        counts = driver.execute_query(
            "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY label",
            database_=db,
        ).records
        for rec in counts:
            print(f"{rec['label']}: {rec['n']}")


if __name__ == "__main__":
    main()
