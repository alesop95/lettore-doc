---
generated-from-commit: 979d674
generated-from-branch: main
generated-date: 2026-06-17
covers-paths:
  - scripts/enrich_graph.py
  - scripts/export_to_taxonomy.py
  - .gitignore
last-verified-commit: cb35334
source-doc: GUIDA-TECNICA.md
---

# Design e sicurezza

## Confine di sicurezza fisico

Due repository con scopi opposti: `lettore-doc` (privato, locale, mai online: codice, dati di lavoro, vault) e il repo pubblico della tassonomia (solo output elaborato e anonimizzato). `export_to_taxonomy.py` e l'unico script che scrive nel repo pubblico, e prima applica l'`anonymization_map` (ragioni sociali in `[AZIENDA_N]`, nomi in `[PERSONA_N]`) prodotta da `enrich_graph.py`. Nessun nome cliente, codice progetto interno o riferimento sensibile attraversa il confine.

## Separazione dei piani dati

`_intermediate/` (derivati rigenerabili, gitignored) contro `vault-output/` (vault navigabile e annotabile a mano, gitignored): si re-indicizza senza perdere annotazioni manuali.

## Segreti

`.env` e `.env.local` gitignored, mai committati (verificato sulla storia). Le path sensibili si risolvono via variabili d'ambiente, mai hardcoded negli script.

Dettaglio in `GUIDA-TECNICA.md` sezioni 1.1-1.3.
