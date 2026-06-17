# Decisioni architetturali (ADR-lite)

> Append-only. Una decisione non si cancella: quando e superata, si aggiunge una voce che la supera citandone il numero.

## ADR-001 — Deterministico prima del linguistico

Contesto: corpora documentali enormi, costo token e necessita di riproducibilita. Decisione: tutto il lavoro deterministico (parsing, regex, grafo, generazione, classificazione) in script Python con stati JSON ispezionabili; l'LLM solo per il salto semantico. Conseguenze: riproducibilita, costo quasi nullo, ispezionabilita degli stati intermedi.

## ADR-002 — Confine di sicurezza fisico tra repo privato e pubblico

Contesto: i documenti sorgente contengono dati sensibili. Decisione: due repository, e un solo script (`export_to_taxonomy.py`) scrive nel pubblico, applicando prima l'`anonymization_map`. Conseguenze: nessun dato sensibile attraversa il confine.

## ADR-003 — Disclosure progressiva a tre livelli

Contesto: una cartella di documenti puo valere oltre un milione di token. Decisione: accesso ai documenti per livelli (scheletro, preview, sezione completa on-demand). Conseguenze: si lavora su corpora grandi a basso costo di contesto.

## ADR-004 — Classificazione per recall e export idempotente

Contesto: mappare i nodi sulla tassonomia in modo ripetibile e senza duplicare. Decisione: recall score con soglie configurabili, ed export idempotente via ID SHA256 in commenti HTML. Conseguenze: pipeline re-eseguibile senza duplicati; gli embeddings semantici restano un'estensione futura (vedi roadmap).
