"""Build the legal subgraph: (:Paragraph)-[:VERWEIST_AUF]->(:Paragraph) from the EStG XML.

Source: the public "gesetze-im-internet.de" XML dump.
  1. Download https://www.gesetze-im-internet.de/estg/xml.zip
  2. Unzip; place the contained BJNR*.xml at data/estg.xml (or pass a path)

Usage:
  uv run python ingest/parse_estg.py [path/to/estg.xml]
"""

from __future__ import annotations

import os
import re
import sys

from dotenv import load_dotenv
from lxml import etree
from neo4j import GraphDatabase

# "§ 10d", "§§ 4 und 5", "§ 32a Absatz 1" — capture number + optional letter suffix.
REF_RE = re.compile(r"§§?\s*(\d+[a-z]?)\b")

# The dump wraps each norm in <norm>; <enbez> holds "§ 9" for paragraph norms.
ENBEZ_RE = re.compile(r"^§\s*(\d+[a-z]?)$")


def extract_references(xml_path: str) -> tuple[list[dict], list[dict]]:
    """Return ([{id, titel}] paragraph nodes, [{source, target}] reference pairs)."""
    tree = etree.parse(xml_path)
    paragraphs: set[str] = set()
    titles: dict[str, str] = {}
    refs: set[tuple[str, str]] = set()

    for norm in tree.iter("norm"):
        enbez = norm.findtext(".//enbez") or ""
        m = ENBEZ_RE.match(enbez.strip())
        if not m:
            continue
        source = m.group(1)
        paragraphs.add(source)
        title = (norm.findtext(".//titel") or "").strip()
        if title:
            titles[source] = title

        text = " ".join(norm.find(".//textdaten").itertext()) if norm.find(".//textdaten") is not None else ""
        for target in REF_RE.findall(text):
            if target != source:  # self-references carry no signal
                refs.add((source, target))

    # Keep only references whose target is an actual EStG paragraph — the regex
    # also catches references into other laws ("§ 3 des UStG"); without this
    # filter those would create phantom EStG nodes.
    pairs = [{"source": s, "target": t} for s, t in sorted(refs) if t in paragraphs]
    nodes = [{"id": p, "titel": titles.get(p, "")} for p in sorted(paragraphs)]
    return nodes, pairs


LOAD_PARAGRAPHS = """
UNWIND $rows AS row
MERGE (p:Paragraph {id: row.id})
SET p.gesetz = 'EStG', p.titel = row.titel
"""

LOAD_REFS = """
UNWIND $rows AS row
MATCH (a:Paragraph {id: row.source}), (b:Paragraph {id: row.target})
MERGE (a)-[:VERWEIST_AUF]->(b)
"""


def main() -> None:
    xml_path = sys.argv[1] if len(sys.argv) > 1 else "data/estg.xml"
    if not os.path.exists(xml_path):
        sys.exit(
            f"Not found: {xml_path}\n"
            "Download https://www.gesetze-im-internet.de/estg/xml.zip, "
            "unzip, and place the BJNR*.xml there (or pass its path)."
        )

    nodes, pairs = extract_references(xml_path)
    print(f"Parsed {len(nodes)} paragraphs, {len(pairs)} cross-references")

    load_dotenv()
    with GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    ) as driver:
        db = os.environ.get("NEO4J_DATABASE")
        driver.execute_query(LOAD_PARAGRAPHS, rows=nodes, database_=db)
        driver.execute_query(LOAD_REFS, rows=pairs, database_=db)
        count = driver.execute_query(
            "MATCH (:Paragraph)-[r:VERWEIST_AUF]->(:Paragraph) RETURN count(r) AS c",
            database_=db,
        ).records[0]["c"]
        print(f"Graph now holds {count} VERWEIST_AUF relationships")


if __name__ == "__main__":
    main()
