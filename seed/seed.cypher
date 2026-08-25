// steuer-graph seed — operational subgraph + join stubs into the legal subgraph.
// Idempotent: everything is MERGE'd on stable ids, safe to re-run.
// Run via: uv run python seed/run_seed.py   (or paste into Aura Query console)

// ---------- Constraints ----------
CREATE CONSTRAINT mandant_id IF NOT EXISTS FOR (m:Mandant) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT fall_id IF NOT EXISTS FOR (f:Fall) REQUIRE f.id IS UNIQUE;
CREATE CONSTRAINT beleg_id IF NOT EXISTS FOR (b:Beleg) REQUIRE b.id IS UNIQUE;
CREATE CONSTRAINT frist_id IF NOT EXISTS FOR (fr:Frist) REQUIRE fr.id IS UNIQUE;
CREATE CONSTRAINT paragraph_id IF NOT EXISTS FOR (p:Paragraph) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT interaction_id IF NOT EXISTS FOR (i:Interaction) REQUIRE i.id IS UNIQUE;

// ---------- 12 Mandanten ----------
UNWIND [
  {id: 'M001', name: 'Greta Lindemann',   typ: 'Privatperson'},
  {id: 'M002', name: 'Jonas Brückner',    typ: 'Privatperson'},
  {id: 'M003', name: 'Sabine Vogelsang',  typ: 'Einzelunternehmerin'},
  {id: 'M004', name: 'Karl-Heinz Ott',    typ: 'Privatperson'},
  {id: 'M005', name: 'Miriam Schattner',  typ: 'Freiberuflerin'},
  {id: 'M006', name: 'Tobias Wendland',   typ: 'Privatperson'},
  {id: 'M007', name: 'Anneliese Kurz',    typ: 'Rentnerin'},
  {id: 'M008', name: 'Deniz Aydemir',     typ: 'Einzelunternehmer'},
  {id: 'M009', name: 'Franziska Hellwig', typ: 'Privatperson'},
  {id: 'M010', name: 'Ulrich Baumgart',   typ: 'Freiberufler'},
  {id: 'M011', name: 'Petra Nowak',       typ: 'Privatperson'},
  {id: 'M012', name: 'Leon Fassbender',   typ: 'Privatperson'}
] AS row
MERGE (m:Mandant {id: row.id})
SET m.name = row.name, m.typ = row.typ;

// ---------- Fälle (one ESt case per Mandant, a few extras) ----------
UNWIND [
  {id: 'F001', mandant: 'M001', art: 'ESt-Erklärung 2025',    status: 'in Bearbeitung'},
  {id: 'F002', mandant: 'M002', art: 'ESt-Erklärung 2025',    status: 'wartet auf Belege'},
  {id: 'F003', mandant: 'M003', art: 'EÜR 2025',              status: 'in Bearbeitung'},
  {id: 'F004', mandant: 'M004', art: 'ESt-Erklärung 2025',    status: 'eingereicht'},
  {id: 'F005', mandant: 'M005', art: 'ESt-Erklärung 2025',    status: 'wartet auf Belege'},
  {id: 'F006', mandant: 'M006', art: 'ESt-Erklärung 2025',    status: 'in Bearbeitung'},
  {id: 'F007', mandant: 'M007', art: 'ESt-Erklärung 2025',    status: 'eingereicht'},
  {id: 'F008', mandant: 'M008', art: 'USt-Voranmeldung Q2',   status: 'in Bearbeitung'},
  {id: 'F009', mandant: 'M009', art: 'ESt-Erklärung 2025',    status: 'wartet auf Belege'},
  {id: 'F010', mandant: 'M010', art: 'ESt-Erklärung 2025',    status: 'in Bearbeitung'},
  {id: 'F011', mandant: 'M011', art: 'ESt-Erklärung 2025',    status: 'neu'},
  {id: 'F012', mandant: 'M012', art: 'ESt-Erklärung 2025',    status: 'neu'},
  {id: 'F013', mandant: 'M003', art: 'USt-Erklärung 2025',    status: 'in Bearbeitung'},
  {id: 'F014', mandant: 'M005', art: 'Einspruch Bescheid 2024', status: 'wartet auf Finanzamt'},
  {id: 'F015', mandant: 'M008', art: 'EÜR 2025',              status: 'neu'}
] AS row
MERGE (f:Fall {id: row.id})
SET f.art = row.art, f.status = row.status
WITH f, row
MATCH (m:Mandant {id: row.mandant})
MERGE (m)-[:HAT_FALL]->(f);

// ---------- 20 Belege (status: 'vorhanden' | 'fehlt') ----------
UNWIND [
  {id: 'B001', fall: 'F001', art: 'Lohnsteuerbescheinigung',      status: 'vorhanden'},
  {id: 'B002', fall: 'F001', art: 'Spendenquittung',              status: 'vorhanden'},
  {id: 'B003', fall: 'F002', art: 'Lohnsteuerbescheinigung',      status: 'vorhanden'},
  {id: 'B004', fall: 'F002', art: 'Handwerkerrechnung',           status: 'fehlt'},
  {id: 'B005', fall: 'F002', art: 'Nachweis Fahrtkosten',         status: 'fehlt'},
  {id: 'B006', fall: 'F003', art: 'Eingangsrechnungen Q1-Q4',     status: 'vorhanden'},
  {id: 'B007', fall: 'F003', art: 'Bewirtungsbelege',             status: 'fehlt'},
  {id: 'B008', fall: 'F004', art: 'Lohnsteuerbescheinigung',      status: 'vorhanden'},
  {id: 'B009', fall: 'F005', art: 'Honorarabrechnungen',          status: 'vorhanden'},
  {id: 'B010', fall: 'F005', art: 'Beitragsnachweis Krankenkasse', status: 'fehlt'},
  {id: 'B011', fall: 'F006', art: 'Lohnsteuerbescheinigung',      status: 'vorhanden'},
  {id: 'B012', fall: 'F006', art: 'Kinderbetreuungskosten',       status: 'vorhanden'},
  {id: 'B013', fall: 'F007', art: 'Rentenbezugsmitteilung',       status: 'vorhanden'},
  {id: 'B014', fall: 'F008', art: 'Ausgangsrechnungen April-Juni', status: 'vorhanden'},
  {id: 'B015', fall: 'F009', art: 'Lohnsteuerbescheinigung',      status: 'fehlt'},
  {id: 'B016', fall: 'F009', art: 'Nebenkostenabrechnung',        status: 'fehlt'},
  {id: 'B017', fall: 'F010', art: 'Honorarabrechnungen',          status: 'vorhanden'},
  {id: 'B018', fall: 'F010', art: 'Fortbildungsnachweise',        status: 'fehlt'},
  {id: 'B019', fall: 'F011', art: 'Lohnsteuerbescheinigung',      status: 'fehlt'},
  {id: 'B020', fall: 'F013', art: 'Umsatzsteuervoranmeldungen',   status: 'vorhanden'}
] AS row
MERGE (b:Beleg {id: row.id})
SET b.art = row.art, b.status = row.status
WITH b, row
MATCH (f:Fall {id: row.fall})
MERGE (f)-[:HAT_BELEG]->(b);

// ---------- 5 Fristen ----------
UNWIND [
  {id: 'FR01', fall: 'F002', art: 'Abgabefrist ESt 2025',        datum: date('2026-09-30')},
  {id: 'FR02', fall: 'F005', art: 'Abgabefrist ESt 2025',        datum: date('2026-09-30')},
  {id: 'FR03', fall: 'F008', art: 'USt-Voranmeldung Q2',         datum: date('2026-09-10')},
  {id: 'FR04', fall: 'F014', art: 'Einspruchsfrist',             datum: date('2026-09-05')},
  {id: 'FR05', fall: 'F009', art: 'Nachreichung Belege',         datum: date('2026-09-15')}
] AS row
MERGE (fr:Frist {id: row.id})
SET fr.art = row.art, fr.datum = row.datum
WITH fr, row
MATCH (f:Fall {id: row.fall})
MERGE (f)-[:HAT_FRIST]->(fr);

// ---------- GOVERNED_BY: join into the legal subgraph ----------
// Paragraph ids match what ingest/parse_estg.py produces ("9", "10", "32a", ...),
// so this works whether the EStG parser has run yet or not.
UNWIND [
  {fall: 'F001', par: '9'},    // Werbungskosten
  {fall: 'F001', par: '10b'},  // Spenden
  {fall: 'F002', par: '35a'},  // Handwerkerleistungen
  {fall: 'F002', par: '9'},
  {fall: 'F003', par: '4'},    // Gewinnbegriff / EÜR
  {fall: 'F005', par: '18'},   // Selbständige Arbeit
  {fall: 'F005', par: '10'},   // Sonderausgaben
  {fall: 'F006', par: '10'},   // Kinderbetreuung
  {fall: 'F007', par: '22'},   // Renteneinkünfte
  {fall: 'F009', par: '19'},   // Nichtselbständige Arbeit
  {fall: 'F009', par: '21'},   // Vermietung
  {fall: 'F010', par: '18'},
  {fall: 'F010', par: '9'},
  {fall: 'F014', par: '32a'}   // Tarif
] AS row
MATCH (f:Fall {id: row.fall})
MERGE (p:Paragraph {id: row.par})
ON CREATE SET p.gesetz = 'EStG'
MERGE (f)-[:GOVERNED_BY]->(p);

// ---------- Interactions: caller memory ----------
UNWIND [
  {id: 'I001', mandant: 'M002', datum: datetime('2026-08-18T10:12:00'), zusammenfassung: 'Fragte nach Status der ESt-Erklärung; Handwerkerrechnung und Fahrtkostennachweis angefordert.'},
  {id: 'I002', mandant: 'M005', datum: datetime('2026-08-20T14:35:00'), zusammenfassung: 'Krankenkassennachweis fehlt noch; Frist 30.09. genannt.'},
  {id: 'I003', mandant: 'M002', datum: datetime('2026-08-24T09:05:00'), zusammenfassung: 'Handwerkerrechnung angekündigt, per Post diese Woche.'},
  {id: 'I004', mandant: 'M007', datum: datetime('2026-08-15T11:47:00'), zusammenfassung: 'Erklärung eingereicht, Bescheid steht aus.'},
  {id: 'I005', mandant: 'M009', datum: datetime('2026-08-22T16:20:00'), zusammenfassung: 'Erinnerung: Lohnsteuerbescheinigung und Nebenkostenabrechnung bis 15.09. nachreichen.'}
] AS row
MERGE (i:Interaction {id: row.id})
SET i.datum = row.datum, i.zusammenfassung = row.zusammenfassung
WITH i, row
MATCH (m:Mandant {id: row.mandant})
MERGE (m)-[:CALLED]->(i);
