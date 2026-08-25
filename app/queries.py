"""Parameterized Cypher — the only place queries live.

No text2cypher at runtime: the voice agent picks an intent, the intent maps to
one of these fixed queries, and user input only ever flows in as parameters.
"""

# Full picture for a status call: cases with their Belege, Fristen, governing
# paragraphs, and the last interactions (caller memory). Mandant is matched by
# name (case-insensitive) or id, so the voice layer can pass what it heard.
STATUS = """
MATCH (m:Mandant)
WHERE m.id = $mandant OR toLower(m.name) CONTAINS toLower($mandant)
OPTIONAL MATCH (m)-[:HAT_FALL]->(f:Fall)
OPTIONAL MATCH (f)-[:HAT_BELEG]->(b:Beleg)
OPTIONAL MATCH (f)-[:HAT_FRIST]->(fr:Frist)
OPTIONAL MATCH (f)-[:GOVERNED_BY]->(p:Paragraph)
WITH m, f,
     collect(DISTINCT {art: b.art, status: b.status}) AS belege,
     collect(DISTINCT {art: fr.art, datum: toString(fr.datum)}) AS fristen,
     collect(DISTINCT ('§ ' + p.id + ' EStG'
       + coalesce(' – ' + coalesce(p.kurzname, CASE WHEN p.titel <> '' THEN p.titel END), ''))) AS paragraphen
WITH m, collect({
       fall: f.id, art: f.art, status: f.status,
       belege: [x IN belege WHERE x.art IS NOT NULL],
       fristen: [x IN fristen WHERE x.art IS NOT NULL],
       paragraphen: paragraphen
     }) AS faelle
OPTIONAL MATCH (m)-[:CALLED]->(i:Interaction)
WITH m, faelle, i ORDER BY i.datum DESC
RETURN m.id AS mandant_id, m.name AS name, m.typ AS typ,
       [f IN faelle WHERE f.fall IS NOT NULL] AS faelle,
       collect({datum: toString(i.datum), zusammenfassung: i.zusammenfassung})[..3] AS letzte_anrufe
"""

# Only what's blocking: Belege with status 'fehlt', plus the deadline pressure.
MISSING = """
MATCH (m:Mandant)
WHERE m.id = $mandant OR toLower(m.name) CONTAINS toLower($mandant)
MATCH (m)-[:HAT_FALL]->(f:Fall)-[:HAT_BELEG]->(b:Beleg {status: 'fehlt'})
OPTIONAL MATCH (f)-[:HAT_FRIST]->(fr:Frist)
RETURN m.name AS name, f.id AS fall, f.art AS fall_art,
       collect(DISTINCT b.art) AS fehlende_belege,
       collect(DISTINCT {art: fr.art, datum: toString(fr.datum)}) AS fristen
"""

# Legal context: what a paragraph is, which cases it governs, and what it
# references / is referenced by in the EStG citation network.
WHY = """
MATCH (p:Paragraph {id: $paragraph})
OPTIONAL MATCH (p)-[:VERWEIST_AUF]->(out:Paragraph)
OPTIONAL MATCH (inp:Paragraph)-[:VERWEIST_AUF]->(p)
OPTIONAL MATCH (f:Fall)-[:GOVERNED_BY]->(p)
OPTIONAL MATCH (m:Mandant)-[:HAT_FALL]->(f)
RETURN p.id AS paragraph, p.titel AS titel,
       coalesce(p.kurzname, CASE WHEN p.titel <> '' THEN p.titel END) AS thema,
       collect(DISTINCT out.id) AS verweist_auf,
       collect(DISTINCT inp.id) AS verwiesen_von,
       collect(DISTINCT {fall: f.id, art: f.art, mandant: m.name}) AS betroffene_faelle
"""

# Write path for the voice layer: one Interaction per call, same Mandant
# matching as STATUS so the agent can pass a spoken name or an id.
LOG_INTERACTION = """
MATCH (m:Mandant)
WHERE m.id = $mandant OR toLower(m.name) CONTAINS toLower($mandant)
CREATE (i:Interaction {id: randomUUID(), datum: datetime(), zusammenfassung: $zusammenfassung})
MERGE (m)-[:CALLED]->(i)
RETURN m.id AS mandant_id, i.id AS interaction_id
"""
